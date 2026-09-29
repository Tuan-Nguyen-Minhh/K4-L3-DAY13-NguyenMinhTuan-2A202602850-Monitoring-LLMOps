# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyen Minh Tuan
- **MSSV:** 2A202602850
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/Tuan-Nguyen-Minhh/K4-L3-DAY13-NguyenMinhTuan-2A202602850-Monitoring-LLMOps
- **Commit SHA cuối:** `9e53177` (docs: correct final commit SHA)
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602850`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

Ghi chú nguồn evidence: `01-03`, `05` là output text của lệnh chạy thật; `04`, `12`, `13`, `14` render từ `data/logs.jsonl` và observations API v2 của Langfuse (kèm file `.json` raw ngay cạnh); `06-11` và `14-incident-trace.png` là ảnh chụp màn hình Langfuse/project cá nhân.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.png` (raw: `04-structured-log.json`) |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` (raw: `12-incident-metric.json`) |
| Incident log | `evidence/13-incident-log.png` (raw: `13-incident-log.json`) |
| Incident trace | `evidence/14-incident-trace.png` (span tree cua CID) + `evidence/14-incident-trace-span.png` (raw span tree) + `evidence/14-incident-trace.json` (raw obs) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (thieu correlation_id, enrichment) | 100/100 (63 records, 19 CIDs, 0 PII leak) | CP1 xong + giu vung sau CP3 |
| `validate_dashboard.py` | chua chay | HOP LE: 6/6 panel | contract giu nguyen, du 6 panel id |
| `pytest` | 22 passed (venv) | 22 passed (.venv, 1.90s) | them child observations van pass; chay bang `.venv\Scripts\python -m pytest -q` |
| Số traces hợp lệ | 0 | 36 traces/2h CP2 (12 moi co du 3 obs) + 5 traces CP3 co du 3 obs | root lab-agent-run + retrieval + llm-generation; CP3 da verify qua observations API v2 |
| Số PII leak | 0 (nho summarize_text, chua co scrub processor) | 0 | email/phone/cccd/card deu REDACTED; trace input/output dung summarize_text |
| Latency P95 / TTFT P95 | | P95 ~3763ms CP2 (12 resp) / challenge p50 2653ms p95 4307ms; TTFT P95 50ms | CP2: 1 cold-start outlier, con lai ~400ms; CP3: rag_slow lam p95 vuot 3000ms |
| Retrieval success rate | | 100% (CP2 12/12, CP3 5/5 tool_success true) | guardrail >=90% dat |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `app/middleware.py:CorrelationIdMiddleware` clear_contextvars dau request, nhan `x-request-id` neu khop `req-[8-hex]` giu lai, nguoc lai sinh `req-<uuid4hex[:8]>`, bind vao structlog contextvars + `request.state`, tra lai qua header `x-request-id` va `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `app/main.py:chat` bind `user_id_hash=sha256(user_id)[:12]`, `session_id`, `feature`, `model=agent.model (claude-sonnet-4-5)`, `env=APP_ENV` truoc log `request_received`; nho `merge_contextvars` nen `response_sent`/`request_failed` tu dong co cung context.
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/logging_config.py:configure_logging` dang ky `scrub_event` truoc `JsonlFileProcessor`/`JSONRenderer`; `scrub_event` scrub moi string trong `payload` + `event` bang `app/pii.py:scrub_text` (email, phone_vn, cccd 12 so, credit_card 16 so). `summarize_text` cung scrub truoc khi dua vao `message_preview`/`answer_preview`, tao 2 lop bao ve.
- **Cách kiểm chứng kết quả:** xoa `data/logs.jsonl` cu (validator doc toan file), chay 10 query `data/sample_queries.jsonl` -> `python scripts/validate_logs.py` dat 100/100 (0 missing, 10 correlation IDs, 0 PII leak); `python -m pytest -q` 22 passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** project `day13-k4-l3a-2A202602850` (Langfuse Cloud). 36 traces/2h CP2 (12 traces moi: req-baseline01, req-candidate01, req-prod-v2, req-prod-rollback-v1, req-bulk-00..07) + 5 traces CP3 (req-bd17da43, req-049fcdfc, req-299c06ac, req-f988892d, req-74e64029) — tat ca deu du 3 observations, verify qua observations API v2 ngay 2026-09-29.

  Evidence: `evidence/06-trace-list.png` (man hinh Tracing cua project ca nhan), `07-trace-waterfall.png` (span tree root → retrieval → llm-generation), `08-trace-metadata.png` (metadata cua node llm-generation).
- **Cấu trúc root/retrieval/generation observations:** `app/agent.py:LabAgent.run` co `@observe(name=lab-agent-run, as_type=agent)` lam root; them `_child_observation` bang `start_as_current_observation`: `retrieval` as_type `retriever` (input=query_preview, metadata correlation/feature/model/session/user_hash/env); `llm-generation` as_type `generation` (model=claude-sonnet-4-5, prompt=managed_prompt, input=prompt_preview, usage input/output/prompt_tokens/completion_tokens/total, cost input/output/total). Parent linkage: ca 2 child co `parent_observation_id=root`, `is_root=False`; latency retrieval ~0ms vs generation ~150-400ms nen waterfall phan biet duoc buoc cham. Khong capture raw PII: root `capture_input/output=False`, child dung `summarize_text` (da scrub).
- **Cách nối trace với log:** cung `correlation_id` (vd `req-prod-v2`): log `data/logs.jsonl` co `correlation_id`, trace metadata/root propagate co `correlation_id`, user_hash, session, feature, model, env. Loc log theo khoang thoi gian -> lay CID -> filter trace theo metadata CID.
- **Prompt name:** `day13-chat` (theo `LANGFUSE_PROMPT_NAME`)
- **Version/label baseline:** v1 labels `baseline,production` (ban dau): `Feature={{feature}} Docs={{docs}} Question={{message}}`
- **Version/label candidate:** v2 labels `candidate,latest`: them dong `Answer concisely in max 3 sentences.`
- **Trace ID của mỗi version:** chay cung input `Explain observability` voi 2 label: CID `req-baseline01` (label baseline -> v1) va `req-candidate01` (label candidate -> v2). Hai trace nay deu du 3 observations; doc bang cach filter `metadata.correlation_id` tren Langfuse UI hoac observations API v2. Evidence anh: `evidence/09-prompt-versions.png` (v1 `#1` labels `production`,`baseline`; v2 `#2` labels `latest`,`candidate`, noi them dong `Answer concisely in max 3 sentences.`).
- **Cách promote và rollback `production`:** `update_prompt(name=day13-chat, version=2, new_labels=[candidate,production])` -> production=v2 (chay `req-prod-v2`); sau do `update_prompt(version=1, [baseline,production])` + `update_prompt(version=2, [candidate])` -> rollback production=v1 (chay `req-prod-rollback-v1`). Evidence: `evidence/10-prompt-rollback.png` — trang prompt cho thay `production` dang nam o version `#1` sau rollback (v2 chi con `latest`,`candidate`).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `config/dashboard.yaml` giu contract (schema 1, 60m, refresh 30s) voi 6 panel: latency (p50/p95/p99 + ttft_p95, ms, thr p95<=3000), traffic (count/rate, rpm, thr>=1), errors (error_rate + breakdown + retrieval success, %, thr err<=2), cost (sum/min+total, usd, thr<=2.5), tokens (sum in/out, tokens, thr<=50000), quality (mean, 0-1, thr>=0.75). Runtime dung `data/logs.jsonl` ve bang matplotlib: `evidence/11-dashboard-overview.png` (12 resp, p95~3763, err 0%, q 0.88). Validator: `HOP LE: 6/6 panel`.
- **SLO và lý do chọn:** `config/slo.yaml` primary `fast_successful_requests`: good=`response_sent and latency<=3000`, total=`request_received`, target 99.5%/28d. Giu 3000ms vi p50 baseline 400ms on dinh, 3000ms bao du tail (rag_slow 2.5s + LLM) ma van chat hon p95 nhieu outlier; khop threshold panel latency.
- **Cách tính error budget:** 100-99.5=0.5%. 1000 req => 5 req xau; 10k req/ngay => 50 req. Het budget som la tin hieu page truoc khi vi pham SLO 28d.
- **Ba alert và runbook tương ứng:** `config/alert_rules.yaml` (symptom-based, duration, severity, owner, slack `#sre-llmops-alerts`, runbook): 1) `llm-high-latency-p95` critical 5m (>3000ms) -> docs/alerts.md#alert-1; 2) `llm-high-error-rate` high 5m (>2%) -> #alert-2; 3) `llm-quality-drop` high 10m (<0.75) -> #alert-3. Runbook chi tiet 3 buoc check (dashboard -> log CID -> trace span) + mitigation trong `docs/alerts.md`.

## 7. Điều tra challenge

### 7.1 Evidence chain: Metric → Log → Trace → Span → Root cause

```
Metric bất thường                    Log có correlation_id              Trace cùng correlation_id         Span gây ảnh hưởng              Root cause
─────────────────────                 ─────────────────────              ─────────────────────────         ──────────────────              ──────────
Panel latency p95=4307ms              10 events trong window              5 traces filter theo CID          retrieval span ~2.5s            STATE["rag_slow"]=True
vuot nguong 3000ms                    5 request_received                 moi trace co 3 observations        chiem ~94% root latency         lam app/mock_rag.py:retrieve()
(window 09:17:50Z-09:18:05Z)         5 response_sent                     root + retrieval + generation    generation ~0.15s binh thuong   time.sleep(2.5) block event loop
                                                                                                        → span retrieval là nguyen nhân
```

### 7.2 Chi tiết từng bước

**Bước 1 — Metric bất thường:**
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4, incident `rag_slow`, affected_feature `monitoring`, 5 queries; file `config/challenge.json` giu nguyen, ignored, khong commit/push)
- **Khoảng thời gian điều tra:** UTC `2026-09-29T09:17:50Z` -> `2026-09-29T09:18:05Z` (local `16:17:49` -> `16:18:05 +07:00`): `inject_incident.py` bat `rag_slow=True`, sau do `load_test.py --challenge --concurrency 5` (5/5 HTTP 200, feature `monitoring`). Evidence: `evidence/12-incident-metric.png`
- **Triệu chứng từ metrics:** panel **latency** bat thuong: `traffic=5`, `latency_p50=2653ms`, `latency_p95=p99=4307ms` vuot nguong dashboard `p95<=3000ms` (alert `llm-high-latency-p95`, critical, 5m). Cac panel khac binh thuong: `ttft_p95=50ms`, `error_breakdown={}`, `quality_avg=0.84`, `tokens 175 in/645 out`, `total_cost 0.0102 USD` -> loai `tool_fail` (se loi) va `cost_spike` (se doi cost/token), chi ve `rag_slow`. Client quan sat 10.1-15.5s cao hon server do request xep hang tuan tu (`time.sleep` chan event loop).

**Bước 2 — Log line và correlation ID liên quan:**
- Loc `data/logs.jsonl` theo window tren thu duoc 10 events (5 `request_received` + 5 `response_sent`), deu `feature=monitoring`, `tool_success=true`.
- Request dai dien **`req-74e64029`** (`session k4-l3a-challenge-s05`): `response_sent ts=2026-09-29T09:18:05.828235Z, latency_ms=2653, ttft_ms=50, tokens 35/158, cost 0.002475, quality 0.8`.
- Cac CID con lai (`req-bd17da43` 4307ms cold-start, `req-049fcdfc`/`req-299c06ac`/`req-f988892d` ~2652-2654ms) cung pattern.
- Evidence: `evidence/13-incident-log.png`

**Bước 3 — Trace ID và span gây ảnh hưởng:**
- Trace **`f96c6ee740befff7bcc964a542a3ce20`** (filter `metadata.correlation_id=req-74e64029`) co 3 observations: root `lab-agent-run` (AGENT) `2.658s` = `retrieval` (RETRIEVER) **`2.506s` (~94%)** + `llm-generation` (GENERATION) `0.152s` binh thuong.
- Ca 4 trace con lai lap lai pattern (`retrieval` 2.502-2.506s, `generation` 0.152-0.154s): `081ecfd418bd1bc9a758624c36485963`, `ea7af7fb8eb092d156edc9ac3015dd70`, `f61b4911bf0627714fee85551d75c775`, `46664657be1dd6d7161ec0ab06ce77a1`.
- Evidence: `evidence/14-incident-trace.png` (span tree + 4 trace anh em), `evidence/07-trace-waterfall.png` (span tree tren UI), `evidence/14-incident-trace.json` (raw observations tu API v2).

**Bước 4 — Root cause và hành động xử lý:**
- **Root cause:** `STATE["rag_slow"]=True` khien `app/mock_rag.py:retrieve()` `time.sleep(2.5)` moi request; ham dong bo lai chay trong endpoint async nen block event loop -> latency server ~2.65s + hieu ung xep hang client 10-15s. Ba bang chung cung chi ve mot nguyen nhan: metric (chi latency tang), log (latency_ms ~2653, khong loi), trace (span retrieval chiem ~94%).
- **Fix action:** `python scripts/inject_incident.py --disable` (da chay: `rag_slow=False`, `/health` xac nhan) de dung sleep 2.5s; kiem tra lai bang 1 load test thuong + `GET /metrics` ve p95 < 3000ms.
- **Preventive measure:** giu alert `llm-high-latency-p95` (5m, critical, Slack `#sre-llmops-alerts`, runbook `docs/alerts.md#alert-1`) + SLO `fast_successful_requests` 99.5%/28d de page som; them timeout + cache + retry cho retrieval, chuyen retrieval cham sang threadpool/async de khong block event loop, giam concurrency mac dinh khi chua fix.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** dat PII scrubber (`scrub_event`) TRUOC `JsonlFileProcessor`/`JSONRenderer` trong pipeline logging thay vi scrub sau khi ghi. Ly do: mot khi PII da serialize xuong `data/logs.jsonl` thi moi ban copy deu nhiem doc; scrub o tang som nhat dam bao khong co duong ghi nao bypass. Lop 2 la `summarize_text` (da scrub) cho preview dua vao log/trace, nen ca 63 records cuoi dat 0 PII leak.
- **Một lỗi/blocker đã gặp:** (1) `python -m pytest` bang system python loi collection 2 file vi thieu deps; (2) query Langfuse trace API cu (`GET /api/public/traces`) tra `410 LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION`; (3) client latency CP3 (10-15s) cao gap 4x server latency (2.6s) gay hoang mang ban dau.
- **Cách tìm nguyên nhân và xử lý:** (1) chuyen sang `.venv\Scripts\python` -> 22 passed; (2) doc message thay the trong loi 410, chuyen sang `GET /api/public/v2/observations` + filter `metadata.correlation_id` -> lay du 3 obs/trace; (3) doi chieu timestamp `request_received/response_sent` thay cac request xu ly tuan tu (ts response truoc == ts request sau) -> ket luan `time.sleep(2.5)` dong bo block event loop gay xep hang, dung server-side latency lam tin hieu chinh.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics (panel latency p95 4307ms > 3000ms, window 09:17:50Z-09:18:05Z) tra loi "he thong co van de gi, khi nao"; loc log trong window lay CID dai dien `req-74e64029` tra loi "request nao bi anh huong"; trace `f96c6ee7...` cua dung CID do so sanh span (retrieval 2.506s vs generation 0.152s) tra loi "buoc nao la nguyen nhan". Chi khi ca 3 cung chi ve retrieval cham thi ket luan moi hop le.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version + label (`baseline/candidate/production`) cho phep thu v2 tren cung input ma khong mat v1, rollback production ve v1 trong vai giay khi candidate loi; token/cost theo doi moi generation phat hien `cost_spike` (output x4) ma latency/error khong thay; SLO 99.5% + error budget 0.5% bien "cham bao nhieu la qua muc" thanh so page cu the qua alert `llm-high-latency-p95`.
- **Điều quan trọng nhất đã học:** redaction phai xay ra truoc serialization, va incident chi duoc ket luan khi metric/log/trace hoi tu ve mot span duy nhat — mot tin hieu don le (chi latency cao) co the bi giai thich sai neu khong co CID noi 3 tang.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) dashboard `11-dashboard-overview.png` moi phan anh runtime CP2 (12 response) chua render lai de lay them 5 request CP3; (2) full trace ID cua 2 prompt version (req-baseline01 / req-candidate01) chua ghi vao report vi Langfuse observations API v2 loc metadata theo thoi gian thay vi gia tri, nen can thao tac tay tren UI; (3) Langfuse khong giu lich su label cu trong UI nen anh rollback chi the hien trang thai sau rollback, phan "truoc rollback" mo ta bang text trong report.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối. (`9e53177`)
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối. (`01-05`, `11-14` da co; `06-10` cho UI)
- [x] Incident evidence nối đúng metric → log → trace. (CID `req-74e64029` / trace `f96c6ee7...` / window 09:17:50Z-09:18:05Z)
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân (`day13-k4-l3a-2A202602850` thay ten project trong moi anh) va khong lo secret (`sk-lf`) hay PII tho. Luu y: Langfuse SDK tu inject `scope.attributes.public_key` (pk-lf, public key khong phai secret) vao metadata cua moi observation nen anh 06/08 hien `pk-lf-...`.
- [x] Repository chạy lại được theo README. (pytest 22 passed, validators 100/100 + 6/6)
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác. (`.env` + `config/challenge.json` ignored, khong tracked; `data/logs.jsonl` khong tracked; submission khong co secret)
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs. (SHA `8a858bc` da push; URL: https://github.com/Tuan-Nguyen-Minhh/K4-L3-DAY13-NguyenMinhTuan-2A202602850-Monitoring-LLMOps)
