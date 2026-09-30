# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests`, tức 99.5% request có `response_sent.latency_ms <= 3000` trong cửa sổ 28 ngày
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000ms` liên tục 5 phút
- Ảnh hưởng tới người dùng: người dùng chờ hơn 3 giây mới có câu trả lời, và error budget latency bị tiêu nhanh
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Latency percentiles and TTFT** để xác nhận P95/P99 tăng từ phút nào, và xem TTFT P95 có tăng theo không. TTFT không đổi nghĩa là phần chậm nằm trước hoặc ngoài LLM.
  2. Lọc `data/logs.jsonl` theo `event == "response_sent"` và `latency_ms > 3000` trong khoảng đó, lấy một `correlation_id` và ghi lại `feature`.
  3. Mở trace trên Langfuse có metadata `correlation_id` trùng, so sánh thời lượng span `retrieval` và `generation` dưới `lab-agent-run` để biết bước nào chiếm phần lớn latency.
- Mitigation tạm thời: nếu `retrieval` chậm thì tắt hoặc khôi phục cấu hình vector store (practice: `python scripts/inject_incident.py --scenario rag_slow --disable`), bật cache hoặc timeout cho retrieval. Nếu `generation` chậm sau khi đổi prompt thì rollback label `production` về version trước. Giảm concurrency khi demo.
- Owner: `student-2A202602536`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailing`
- Severity: `critical`
- Duration: `3m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests`, cùng guardrail `error_rate_pct_max = 2` và `retrieval_success_rate_pct_min = 90`
- Điều kiện và thời gian duy trì: `request_failed / request_received * 100 > 2%` HOẶC `tool_success_rate_pct(retrieval) < 90%` liên tục 3 phút
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500 hoặc câu trả lời không có context. Mỗi request lỗi tiêu thẳng error budget.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Error rate and retrieval success**, xem dòng *Error breakdown by type* để biết loại lỗi (ví dụ `RuntimeError`) và thời điểm bắt đầu.
  2. Lọc `data/logs.jsonl` theo `event == "request_failed"`, đọc `error_type`, `tool_name`, `tool_success` và `payload.detail`, rồi lấy một `correlation_id`.
  3. Mở trace có cùng `correlation_id`, tìm observation có level `ERROR` (thường là `retrieval`) và đọc status message.
- Mitigation tạm thời: chuyển sang fallback answer không cần retrieval hoặc retry có backoff cho vector store. Practice: `python scripts/inject_incident.py --scenario tool_fail --disable`. Nếu lỗi xuất hiện ngay sau một deploy hoặc prompt mới thì rollback.
- Owner: `student-2A202602536`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max = 2.5`. Baseline cost khoảng 0.002 USD/request, ngưỡng cảnh báo là 0.005 USD/request (khoảng 2.5 lần baseline).
- Điều kiện và thời gian duy trì: `avg(response_sent.cost_usd) > 0.005` HOẶC chi phí ước tính theo ngày `> 2.5 USD` liên tục 10 phút
- Ảnh hưởng tới người dùng: chưa ảnh hưởng trực tiếp, nhưng câu trả lời dài bất thường và ngân sách vận hành bị đốt nhanh
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Cost over time** và **Input and output tokens**, xác định cost tăng do `tokens_in` (prompt/context dài) hay `tokens_out` (output dài), trong khi panel **Request traffic** không tăng tương ứng.
  2. Lọc `data/logs.jsonl` theo `response_sent` có `cost_usd` hoặc `tokens_out` cao, lấy `correlation_id`.
  3. Mở trace cùng `correlation_id` và xem observation `generation`: usage input/output, cost, model, `prompt_version` và `prompt_label`.
- Mitigation tạm thời: rollback prompt nếu version mới làm output dài ra, đặt `max_tokens` hoặc giới hạn độ dài output, hoặc chuyển feature ít quan trọng sang model rẻ hơn. Practice: `python scripts/inject_incident.py --scenario cost_spike --disable`.
- Owner: `student-2A202602536`
