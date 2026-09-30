# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Thị Hạ
- **MSSV:** 2A202602536
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602536`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Baseline (trước khi sửa) | `evidence/00-baseline-*.txt` |
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100: 20 record thiếu `correlation_id`, 20 record thiếu enrichment, 0 correlation ID ([baseline](evidence/00-baseline-validate-logs.txt)) | 100/100 ([kết quả](evidence/02-log-validator.txt)) | Đạt sau khi làm middleware, bind context và PII processor |
| `validate_dashboard.py` | HỢP LỆ 6/6 (contract có sẵn) | HỢP LỆ 6/6 | Contract không đổi; dashboard runtime dựng bằng `scripts/build_dashboard.py` |
| `pytest` | 22 passed | 35 passed | Thêm tests cho correlation ID, context leak, PII (CCCD, thẻ, passport, regression), thứ tự processor và phần tổng hợp dashboard |
| Số traces hợp lệ | | | |
| Số PII leak | 0 (validator) | 0 | Tự test phát hiện thêm lỗi regex thẻ khi CCCD đứng trước số thẻ và đã sửa (xem mục 4) |
| Latency P95 / TTFT P95 | ~151 ms / 50 ms (`latency_ms`/`ttft_ms` trong log baseline) | | Điền sau lần chạy cuối |
| Retrieval success rate | | | |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `app/middleware.py` gọi `clear_contextvars()` đầu mỗi request để không rò context. Nếu client gửi `x-request-id` hợp lệ (`[A-Za-z0-9._-]{1,64}`) thì dùng lại, nếu không thì sinh `req-<8 hex>`. ID được bind vào structlog contextvars và `request.state`, truyền vào `LabAgent.run` để ghi vào trace metadata, rồi trả lại qua header `x-request-id` cùng `x-response-time-ms` và trong body response.
- **Các metadata được ghi vào structured log:** `app/main.py` bind `user_id_hash` (SHA-256, 12 ký tự, không log user_id thô), `session_id`, `feature`, `model`, `env` trước log `request_received`. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` (`app/logging_config.py`) chạy sau `format_exc_info` và trước `JsonlFileProcessor`/`JSONRenderer`. Processor scrub đệ quy mọi field chuỗi, trừ các field do hệ thống sinh (`ts`, `level`, `correlation_id`, `user_id_hash`). `app/pii.py` có pattern cho email, thẻ, SĐT VN, CCCD và passport.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100, `tests/test_correlation_logging.py` (header, ID tái sử dụng, không rò context giữa 2 request, không còn PII trong file log) và [05-pii-redaction](evidence/05-pii-redaction.txt). Khi tự test runtime, tôi phát hiện `079123456789 4111-1111-1111-1111` bị regex thẻ match nhầm (`0791 2345 6789 4111`), để lộ `-1111-1111-1111`. Tôi sửa bằng cách đặt pattern CCCD chạy **trước** pattern thẻ. Tôi không siết regex thẻ vì cách đó sẽ bỏ sót thẻ viết lẫn dấu phân cách như `4111 1111-1111 1111`. Có test hồi quy cho cả hai trường hợp. Processor scrub được đặt sau `format_exc_info` để che cả traceback exception, và `tests/test_logging_processors.py` kiểm tra thứ tự này.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `python scripts/build_dashboard.py [--watch]` đọc `data/logs.jsonl` theo đúng contract `config/dashboard.yaml` và sinh `data/dashboard.html`: time range 60 phút, auto-refresh 30 giây, bucket theo phút. Mỗi panel có đơn vị, đường threshold và trạng thái đạt/vượt. Sáu panel gồm Latency P50/P95/P99 + TTFT P95; Traffic req/min; Error rate + retrieval success + breakdown theo `error_type`; Cost theo phút + lũy kế; Tokens in/out lũy kế; Quality mean.
- **SLO và lý do chọn:** `config/slo.yaml` đặt 99.5% request có `response_sent` với `latency_ms <= 3000` trong 28 ngày. Baseline `latency_ms` khoảng 150–152 ms (cả tuần tự lẫn concurrency 5), nên 3000 ms là ngưỡng rộng, gần 20 lần baseline. Hạn chế đã biết: khi chạy thử challenge, request chậm có `latency_ms` khoảng 2650 ms, vượt ngưỡng 2000 ms của challenge nhưng chưa vượt 3000 ms, nên SLO và `HighLatencyP95` **không** phát hiện được. Ngoài ra `latency_ms` chỉ đo thời gian trong agent; client đo tới khoảng 13 s vì endpoint async gọi `agent.run` đồng bộ nên các request bị xếp hàng. Hai điểm này được phân tích ở mục 7.
- **Cách tính error budget:** 100% − 99.5% = 0.5%. Với 10,000 request/28 ngày thì tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms. Chi tiết burn rate xem trong `config/slo.yaml`.
- **Ba alert và runbook tương ứng:** `config/alert_rules.yaml` + [`docs/alerts.md`](../docs/alerts.md), tất cả gửi Slack `#k4-l3b-alerts`, owner `student-2A202602536`: (1) `HighLatencyP95`, warning, P95 > 3000 ms trong 5m; (2) `HighErrorRateOrRetrievalFailing`, critical, error rate > 2% hoặc retrieval success < 90% trong 3m; (3) `CostPerRequestSpike`, warning, cost trung bình > 0.005 USD/request hoặc chi phí dự kiến > 2.5 USD/ngày trong 10m.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
