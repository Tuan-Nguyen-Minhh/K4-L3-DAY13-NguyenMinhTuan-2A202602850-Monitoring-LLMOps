from __future__ import annotations

import os
import time
from contextlib import nullcontext
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, observe, propagate_attributes, tracing_enabled


def _child_observation(client, **kwargs):
    """Return a child-observation CM, or a no-op when SDK/mock lacks the API."""
    fn = getattr(client, "start_as_current_observation", None)
    if not callable(fn):
        return nullcontext(None)
    try:
        return fn(**kwargs)
    except Exception:
        return nullcontext(None)


def _safe_update(obs, **kwargs):
    if obs is None:
        return
    try:
        obs.update(**kwargs)
    except Exception:
        pass


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(name="lab-agent-run", as_type="agent", capture_input=False, capture_output=False)
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        langfuse_client = get_langfuse_client()
        with propagate_attributes(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
            trace_name="day13-agent-request",
            environment=os.getenv("APP_ENV", "dev"),
            metadata={
                "feature": feature,
                "model": self.model,
                "correlation_id": correlation_id,
            },
        ):
            started = time.perf_counter()
            env_name = os.getenv("APP_ENV", "dev")
            user_hash = hash_user_id(user_id)
            query_preview = summarize_text(message)
            # Child observation: retrieval (retriever/span)
            with _child_observation(
                langfuse_client,
                name="retrieval",
                as_type="retriever",
                input=query_preview,
                metadata={
                    "correlation_id": correlation_id,
                    "feature": feature,
                    "model": self.model,
                    "session_id": session_id,
                    "user_id_hash": user_hash,
                    "env": env_name,
                },
            ) as retr_obs:
                docs = retrieve(message)
                _safe_update(
                    retr_obs,
                    output={"doc_count": len(docs)},
                    metadata={
                        "correlation_id": correlation_id,
                        "doc_count": len(docs),
                    },
                )
            prompt = resolve_prompt(
                langfuse_client,
                feature=feature,
                docs=docs,
                message=message,
                enabled=tracing_enabled(),
            )
            langfuse_client.update_current_span(
                metadata={
                    "doc_count": len(docs),
                    "query_preview": summarize_text(message),
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error or "",
                },
                version=prompt.version,
            )
            # TODO (CP2): instrument retrieve() and FakeLLM.generate() as child
            # observations. The nested generation must receive prompt, usage and cost.
            prompt_preview = summarize_text(prompt.text)
            with _child_observation(
                langfuse_client,
                name="llm-generation",
                as_type="generation",
                model=self.model,
                prompt=prompt.managed_prompt,
                input=prompt_preview,
                metadata={
                    "correlation_id": correlation_id,
                    "feature": feature,
                    "model": self.model,
                    "session_id": session_id,
                    "user_id_hash": user_hash,
                    "env": env_name,
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                },
            ) as gen_obs:
                with propagate_attributes(prompt=prompt.managed_prompt):
                    response = self.llm.generate(prompt.text)
                gen_input_cost = (response.usage.input_tokens / 1_000_000) * 3
                gen_output_cost = (response.usage.output_tokens / 1_000_000) * 15
                _safe_update(
                    gen_obs,
                    output=summarize_text(response.text),
                    usage_details={
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total": response.usage.input_tokens + response.usage.output_tokens,
                    },
                    cost_details={
                        "input": round(gen_input_cost, 6),
                        "output": round(gen_output_cost, 6),
                        "total": round(gen_input_cost + gen_output_cost, 6),
                    },
                    model=self.model,
                    metadata={
                        "correlation_id": correlation_id,
                        "prompt_name": prompt.name,
                        "prompt_label": prompt.label,
                        "prompt_version": prompt.version,
                    },
                )
                if gen_obs is None:
                    updater = getattr(langfuse_client, "update_current_generation", None)
                    if callable(updater):
                        try:
                            updater(
                                output=summarize_text(response.text),
                                usage_details={
                                    "input": response.usage.input_tokens,
                                    "output": response.usage.output_tokens,
                                },
                                cost_details={
                                    "total": round(gen_input_cost + gen_output_cost, 6),
                                },
                                model=self.model,
                                prompt=prompt.managed_prompt,
                                metadata={"correlation_id": correlation_id},
                            )
                        except Exception:
                            pass
            quality_score = self._heuristic_quality(message, response.text, docs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens)

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
