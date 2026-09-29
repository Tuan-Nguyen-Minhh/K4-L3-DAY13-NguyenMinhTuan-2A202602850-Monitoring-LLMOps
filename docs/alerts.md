# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: llm-high-latency-p95
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack `#sre-llmops-alerts`
- SLI/SLO liên quan: fast_successful_requests (response_sent.latency_ms p95 <= 3000ms, target 99.5%/28d)
- Điều kiện và thời gian duy trì: `percentile(latency_ms, 95) > 3000ms` liên tục 5 phút trên panel latency (time range 60m, unit ms)
- Ảnh hưởng tới người dùng: request chậm, TTFT cao, timeout phía client; tail latency xấu dù P50 vẫn tốt
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel latency: xác định khoảng thời gian P95 vượt ngưỡng và xem TTFT P95 có tăng cùng không (retrieval hay LLM).
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy `correlation_id` của request `latency_ms` cao nhất.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh span `retrieval` vs `llm-generation` để khoanh vùng bước chậm.
- Mitigation tạm thời: tắt incident practice nếu đang bật (`inject_incident.py --disable`); giảm concurrency/load test; rollback prompt về v1 nếu v2 mới promote gây chậm.
- Owner: backend-oncall

## Alert 2

- Tên: llm-high-error-rate
- Severity: high
- Duration: 5m
- Kênh thông báo: Slack `#sre-llmops-alerts`
- SLI/SLO liên quan: fast_successful_requests + guardrail error_rate_pct_max 2% (panel errors, unit percent)
- Điều kiện và thời gian duy trì: `request_failed / request_received * 100 > 2%` liên tục 5 phút; kèm breakdown `error_type` và `tool_success_rate`
- Ảnh hưởng tới người dùng: request 500, retrieval timeout, mất câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Xem panel errors: error_rate_pct, breakdown theo `error_type`, retrieval success rate có rớt dưới 90% không.
  2. Lọc log `event == "request_failed"`, lấy `correlation_id` + `error_type` + `tool_name`.
  3. Mở trace cùng ID, xem span lỗi (retrieval timeout vs generation) và kiểm tra `/incidents` status.
- Mitigation tạm thời: disable incident `tool_fail`; kiểm tra vector store/dependency; giữ traffic thấp tới khi error < 2%.
- Owner: backend-oncall

## Alert 3

- Tên: llm-quality-drop
- Severity: high
- Duration: 10m
- Kênh thông báo: Slack `#sre-llmops-alerts`
- SLI/SLO liên quan: quality proxy `mean(quality_score) >= 0.75` (panel quality, unit score_0_to_1)
- Điều kiện và thời gian duy trì: `mean(quality_score) < 0.75` liên tục 10 phút (cửa sổ dài hơn để tránh nhiễu từng request)
- Ảnh hưởng tới người dùng: câu trả lời ngắn/rỗng, sai context, PII bị redact quá mức làm giảm hữu ích
- Ba bước kiểm tra đầu tiên:
  1. Xem panel quality + tokens/cost: quality rớt có đi cùng tokens_out bất thường hoặc cost spike không.
  2. Lọc log `response_sent` quality thấp, lấy `correlation_id` và `answer_preview`.
  3. Mở trace cùng ID, kiểm tra `prompt_name/label/version`, `doc_count`, `query_preview` để xem prompt hay retrieval gây ra.
- Mitigation tạm thời: rollback label `production` về prompt v1 ổn định; kiểm tra corpus retrieval; không tăng temperature/budget vội.
- Owner: llm-quality-owner
