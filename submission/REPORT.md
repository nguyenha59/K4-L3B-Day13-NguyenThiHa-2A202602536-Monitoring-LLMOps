# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Thị Hạ
- **MSSV:** 2A202602536
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/nguyenha59/K4-L3B-Day13-NguyenThiHa-2A202602536-Monitoring-LLMOps
- **Commit SHA cuối:** _(điền sau commit cuối)_
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602536`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Baseline (trước khi sửa) | [pytest](evidence/00-baseline-pytest.txt), [validate_logs](evidence/00-baseline-validate-logs.txt), [validate_dashboard](evidence/00-baseline-validate-dashboard.txt), [load_test](evidence/00-baseline-load-test.txt) |
| Pytest cuối | [evidence/01-pytest.txt](evidence/01-pytest.txt) |
| Log validator | [evidence/02-log-validator.txt](evidence/02-log-validator.txt) |
| Dashboard validator | [evidence/03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) |
| Structured log | [evidence/04-structured-log.txt](evidence/04-structured-log.txt) |
| PII redaction | [evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) + danh sách 41 trace [06-trace-list.txt](evidence/06-trace-list.txt) |
| Trace waterfall | [07-08-trace-waterfall-metadata.png](evidence/07-08-trace-waterfall-metadata.png) (cây span bên trái) + [07-trace-waterfall.txt](evidence/07-trace-waterfall.txt) |
| Trace metadata | [07-08-trace-waterfall-metadata.png](evidence/07-08-trace-waterfall-metadata.png) (metadata bên phải; public key đã che) + token/cost [08-trace-metadata.txt](evidence/08-trace-metadata.txt) |
| Prompt versions | [evidence/09-prompt-versions.png](evidence/09-prompt-versions.png) |
| Prompt rollback | Trước: [10a-prompt-before-v1.png](evidence/10a-prompt-before-v1.png) (production → v1) · Promote: [10b-prompt-promoted-v2.png](evidence/10b-prompt-promoted-v2.png) (production → v2) · Rollback: [10c-prompt-rollback-v1.png](evidence/10c-prompt-rollback-v1.png) (production → v1) + trace IDs [evidence/10-prompt-trace-ids.txt](evidence/10-prompt-trace-ids.txt) |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [evidence/12-incident-metric.png](evidence/12-incident-metric.png) + số liệu [evidence/12-incident-metric.txt](evidence/12-incident-metric.txt) |
| Incident log | [evidence/13-incident-log.txt](evidence/13-incident-log.txt) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) + span latency [14-incident-trace.txt](evidence/14-incident-trace.txt) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100: 20 record thiếu `correlation_id`, 20 record thiếu enrichment, 0 correlation ID ([baseline](evidence/00-baseline-validate-logs.txt)) | 100/100 ([kết quả](evidence/02-log-validator.txt)) | Đạt sau khi làm middleware, bind context và PII processor |
| `validate_dashboard.py` | HỢP LỆ 6/6 (contract có sẵn) | HỢP LỆ 6/6 | Contract không đổi; dashboard runtime dựng bằng `scripts/build_dashboard.py` |
| `pytest` | 22 passed | 35 passed | Thêm tests cho correlation ID, context leak, PII (CCCD, thẻ, passport, regression), thứ tự processor và phần tổng hợp dashboard |
| Số traces hợp lệ | — (starter chỉ có root observation) | 41 | Mỗi trace có đủ `lab-agent-run`/`retrieval`/`generation` và `correlation_id`: 16 trace từ CP2 ([IDs](evidence/10-prompt-trace-ids.txt)) và 25 trace từ CP3 ([IDs](evidence/14-incident-trace.txt)) |
| Số PII leak | 0 (validator) | 0 | Tự test phát hiện thêm lỗi regex thẻ khi CCCD đứng trước số thẻ và đã sửa (xem mục 4) |
| Latency P95 / TTFT P95 | ~151 ms / 50 ms (`latency_ms`/`ttft_ms` trong log baseline) | Trạng thái ổn định: 153 ms / 50 ms (30 request, không tính sự cố và cold start). Trong sự cố CP3: 2652 ms / 50 ms | Toàn bộ `data/logs.jsonl` có P95 = 2652 ms vì gồm cả 5 request sự cố và 9 request cold start 1,3–2,2 s (xem mục 8) |
| Retrieval success rate | 100% (10/10) | 100% (44/44) | `rag_slow` làm retrieval **chậm** chứ không làm retrieval **lỗi**, nên metric này không đổi trong sự cố |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `app/middleware.py` gọi `clear_contextvars()` đầu mỗi request để không rò context. Nếu client gửi `x-request-id` hợp lệ (`[A-Za-z0-9._-]{1,64}`) thì dùng lại, nếu không thì sinh `req-<8 hex>`. ID được bind vào structlog contextvars và `request.state`, truyền vào `LabAgent.run` để ghi vào trace metadata, rồi trả lại qua header `x-request-id` cùng `x-response-time-ms` và trong body response.
- **Các metadata được ghi vào structured log:** `app/main.py` bind `user_id_hash` (SHA-256, 12 ký tự, không log user_id thô), `session_id`, `feature`, `model`, `env` trước log `request_received`. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` (`app/logging_config.py`) chạy sau `format_exc_info` và trước `JsonlFileProcessor`/`JSONRenderer`. Processor scrub đệ quy mọi field chuỗi, trừ các field do hệ thống sinh (`ts`, `level`, `correlation_id`, `user_id_hash`). `app/pii.py` có pattern cho email, thẻ, SĐT VN, CCCD và passport.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100, `tests/test_correlation_logging.py` (header, ID tái sử dụng, không rò context giữa 2 request, không còn PII trong file log) và [05-pii-redaction](evidence/05-pii-redaction.txt). Khi tự test runtime, tôi phát hiện `079123456789 4111-1111-1111-1111` bị regex thẻ match nhầm (`0791 2345 6789 4111`), để lộ `-1111-1111-1111`. Tôi sửa bằng cách đặt pattern CCCD chạy **trước** pattern thẻ. Tôi không siết regex thẻ vì cách đó sẽ bỏ sót thẻ viết lẫn dấu phân cách như `4111 1111-1111 1111`. Có test hồi quy cho cả hai trường hợp. Processor scrub được đặt sau `format_exc_info` để che cả traceback exception, và `tests/test_logging_processors.py` kiểm tra thứ tự này.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** `.env` dùng key pair của project `day13-k4-l3b-2A202602536`. Tôi truy vấn `GET /api/public/v2/observations` bằng chính key đó và thấy 41 traces ([06-trace-list.txt](evidence/06-trace-list.txt), ảnh [06-trace-list.png](evidence/06-trace-list.png)). Mỗi trace có `correlation_id` trùng với một dòng trong `data/logs.jsonl` do tôi chạy, `user_id` là hash 12 ký tự và `environment=dev`. Trace ID theo từng bước: [10-prompt-trace-ids](evidence/10-prompt-trace-ids.txt) (CP2) và [14-incident-trace](evidence/14-incident-trace.txt) (CP3).
- **Cấu trúc root/retrieval/generation observations:** trace `day13-agent-request` → `lab-agent-run` (agent, metadata `feature`, `model`, `correlation_id`, `prompt_*`, `query_preview` đã scrub) → `retrieval` (retriever, output `doc_count` + preview tài liệu) và `generation` (generation, có `model`, `usage_details` input/output/total, `cost_details`, `completion_start_time` cho TTFT và link tới prompt managed). Không bật `capture_input/output` tự động; input/output của generation chỉ là preview đã qua `summarize_text` (scrub PII). Cả 41 traces đều có đủ 3 observation (41/41/41), xem ảnh [07-08-trace-waterfall-metadata.png](evidence/07-08-trace-waterfall-metadata.png).
- **Cách nối trace với log:** `correlation_id` do middleware sinh được truyền vào `LabAgent.run` và gắn vào trace metadata qua `propagate_attributes`. Ví dụ `req-bd24d9d9`: log `request_received`/`response_sent` (tokens_in=32, latency_ms=1307) ↔ trace `84170c036bdbb600a6c074001dc49c99`. Trên Langfuse, lọc theo metadata `correlation_id` để tìm trace của một dòng log.
- **Prompt name:** `day13-chat` (text prompt, giữ 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** version 1, labels `baseline` (+ `production` ban đầu và sau rollback). Nội dung là template gốc.
- **Version/label candidate:** version 2, label `candidate` (+ `latest`). Thêm dòng `Answer concisely in at most 3 sentences.`, nên cùng input thì `tokens_in` tăng từ 32 lên 43.
- **Trace ID của mỗi version** (cùng input `Explain why metrics traces and logs work together`, feature `qa`):
  - `baseline` → v1: `ed8886388574764a5902d56c67eb98e7` (`req-9cc44aef`)
  - `candidate` → v2: `3ddc0d8d645d5bbdfbe4516622a209be` (`req-7ab6921a`)
  - `production` trước khi promote → v1: `cc622dd00f3eb0426e67e3eed6b7df5d` (`req-71ffabff`)
  - `production` sau khi promote → v2: `8aa7bd4843b95e917784c31f73e63515` (`req-899a01c2`), `63784068630f383a9f19a3859504cc5f` (`req-c7c1271d`)
  - `production` sau rollback → v1: `84170c036bdbb600a6c074001dc49c99` (`req-bd24d9d9`)
- **Cách promote và rollback `production`:** app chỉ đọc `LANGFUSE_PROMPT_LABEL=production`, nên đổi version không cần sửa code hay deploy. Promote: gắn label `production` cho version 2 (Langfuse tự gỡ label khỏi version 1). Rollback lúc 2026-09-30T16:48:35Z: `PATCH /api/public/v2/prompts/day13-chat/versions/1` với `newLabels=["baseline","production"]`. Kết quả: v1 = `[baseline, production]`, v2 = `[latest, candidate]`. Do SDK cache prompt 60 giây (`cache_ttl_seconds=60`) và sau khi hết hạn vẫn trả bản cũ trong lúc refresh nền, tôi restart API để request kế tiếp chắc chắn lấy v1. Trong production thật, sau rollback cần chờ hết TTL rồi mới kiểm chứng bằng trace `prompt_version`. Toàn bộ 10 request load test sau đó đều ghi `production` / version 1. Ảnh: [09-prompt-versions](evidence/09-prompt-versions.png); trước/promote/rollback: [10a](evidence/10a-prompt-before-v1.png) → [10b](evidence/10b-prompt-promoted-v2.png) → [10c](evidence/10c-prompt-rollback-v1.png).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `python scripts/build_dashboard.py [--watch]` đọc `data/logs.jsonl` theo đúng contract `config/dashboard.yaml` và sinh `data/dashboard.html`: time range 60 phút, auto-refresh 30 giây, bucket theo phút. Mỗi panel có đơn vị, đường threshold và trạng thái đạt/vượt. Sáu panel gồm Latency P50/P95/P99 + TTFT P95; Traffic req/min; Error rate + retrieval success + breakdown theo `error_type`; Cost theo phút + lũy kế; Tokens in/out lũy kế; Quality mean.
- **SLO và lý do chọn:** `config/slo.yaml` đặt 99.5% request có `response_sent` với `latency_ms <= 3000` trong 28 ngày. Baseline `latency_ms` khoảng 150–152 ms (cả tuần tự lẫn concurrency 5), nên 3000 ms là ngưỡng rộng, gần 20 lần baseline. Hạn chế đã biết: khi chạy thử challenge, request chậm có `latency_ms` khoảng 2650 ms, vượt ngưỡng 2000 ms của challenge nhưng chưa vượt 3000 ms, nên SLO và `HighLatencyP95` **không** phát hiện được. Ngoài ra `latency_ms` chỉ đo thời gian trong agent; client đo tới khoảng 13 s vì endpoint async gọi `agent.run` đồng bộ nên các request bị xếp hàng. Hai điểm này được phân tích ở mục 7.
- **Cách tính error budget:** 100% − 99.5% = 0.5%. Với 10,000 request/28 ngày thì tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms. Chi tiết burn rate xem trong `config/slo.yaml`.
- **Ba alert và runbook tương ứng:** `config/alert_rules.yaml` + [`docs/alerts.md`](../docs/alerts.md), tất cả gửi Slack `#k4-l3b-alerts`, owner `student-2A202602536`: (1) `HighLatencyP95`, warning, P95 > 3000 ms trong 5m; (2) `HighErrorRateOrRetrievalFailing`, critical, error rate > 2% hoặc retrieval success < 90% trong 3m; (3) `CostPerRequestSpike`, warning, cost trung bình > 0.005 USD/request hoặc chi phí dự kiến > 2.5 USD/ngày trong 10m.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, `config/challenge.json` của lớp L3B). Chạy `python scripts/inject_incident.py` rồi `python scripts/load_test.py --challenge --concurrency 5`, trước và sau đó chạy workload thường để có mốc so sánh.
- **Khoảng thời gian điều tra:** 2026-09-30 16:56:52–16:57:12 UTC. Sự cố kéo dài từ 16:56:55 (request challenge đầu tiên) tới 16:57:09 (tắt incident).
- **Triệu chứng từ metrics:** panel Latency cho thấy `latency_ms` P95 tăng từ 179 ms (10 request ngay trước) lên **2652 ms** trong sự cố, vượt ngưỡng 2000 ms của challenge. Sau khi tắt incident, P95 quay về 153 ms. Các metric khác gần như không đổi: TTFT P95 giữ 50 ms, error rate 0%, retrieval success 100%, token và cost bình thường (cost TB 0.0019 USD so với 0.0021 USD), quality 0.84 so với 0.88. Cả 5 request bất thường đều có `feature=monitoring`. Vì TTFT không tăng mà tổng latency tăng, thời gian bị mất nằm **trước** bước generation. Số liệu: [12-incident-metric.txt](evidence/12-incident-metric.txt), ảnh [12-incident-metric.png](evidence/12-incident-metric.png).
- **Log line và correlation ID liên quan:** `python scripts/find_anomalies.py --since 2026-09-30T16:56 --latency-ms 2000` trả về đúng 5 log `response_sent`, tất cả `latency_ms=2652`, `ttft_ms=50`, `tool_success=true`. Request đại diện là `correlation_id=req-2fe0a88d`: `request_received` lúc 16:56:55.908Z, `response_sent` lúc 16:56:58.563Z, `latency_ms=2652`, `session_id=k4-l3b-challenge-s01`. Log đầy đủ: [13-incident-log.txt](evidence/13-incident-log.txt).
- **Trace ID và span gây ảnh hưởng:** trace `41268779ad0619b86a9301d11c4e916f` có metadata `correlation_id=req-2fe0a88d`. Trong trace, `lab-agent-run` mất 2.653 s, trong đó **`retrieval` 2.502 s (94%)**, còn `generation` 0.151 s như bình thường. Cả 5 trace `monitoring` đều có retrieval khoảng 2.50 s. Các trace `qa`/`summary` trước và sau sự cố có retrieval ≤ 0.006 s. Bảng đầy đủ: [14-incident-trace.txt](evidence/14-incident-trace.txt), ảnh [14-incident-trace.png](evidence/14-incident-trace.png).
- **Root cause:** bước retrieval (RAG/vector store) chậm thêm khoảng 2.5 s mỗi request trong khi vẫn trả kết quả thành công. Đây là incident `rag_slow`; trong code, `app/mock_rag.py` gọi `time.sleep(2.5)` khi cờ bật. Generation, prompt (vẫn v1) và token không đổi nên không phải nguyên nhân. Sự cố bị khuếch đại ở phía client: `load_test` đo 8.0–13.3 s dù `latency_ms` chỉ 2.65 s. Log cho thấy 5 request đồng thời được xử lý **tuần tự**, request sau bắt đầu đúng lúc request trước kết thúc (16:56:55.9 → 58.6 → 01.2 → 03.9 → 06.5). Lý do: `/chat` là `async def` nhưng gọi `agent.run` đồng bộ, nên `sleep` trong retrieval chặn event loop.
- **Fix action:** tắt nguồn gây chậm (`python scripts/inject_incident.py --disable`; trong production thật là failover/khôi phục vector store). Sau đó xác minh bằng dữ liệu: 10 request sau 16:57:09 có P95 = 153 ms, retrieval ≤ 0.002 s trong trace. Cần sửa thêm phần khuếch đại: chạy agent trong threadpool (`await run_in_threadpool(agent.run, ...)`) hoặc đổi `/chat` sang `def` để một request chậm không chặn các request khác.
- **Preventive measure:** (1) SLO/alert hiện tại **không bắt được** sự cố này: 2652 ms < ngưỡng 3000 ms của `HighLatencyP95`, còn retrieval success vẫn 100%. Cần thêm alert theo độ trễ của retrieval, ví dụ P95 retrieval > 1000 ms trong 5 phút, hoặc hạ ngưỡng latency theo từng feature về 2000 ms như challenge. (2) Ghi `retrieval_ms` vào log `response_sent` để dashboard/alert thấy được chậm ở bước nào mà không cần mở trace. (3) Đặt timeout cho retrieval và fallback khi vượt ngưỡng. (4) Thêm test tải với concurrency > 1 để phát hiện request bị xếp hàng. (5) Đo latency ở middleware (`x-response-time-ms`) cho SLO, vì `latency_ms` trong agent không tính thời gian chờ.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** trong trace, tôi tắt `capture_input`/`capture_output` tự động của `@observe` ở cả 3 observation. Thay vào đó, tôi chỉ ghi preview đã qua `summarize_text` (scrub PII) cùng metadata an toàn (`correlation_id`, `feature`, `model`, `prompt_*`, token, cost). Langfuse là dịch vụ bên ngoài, nên nếu capture raw prompt thì email/SĐT/CCCD người dùng nhập sẽ rời khỏi hệ thống, và scrubber của structlog không bảo vệ được đường này. Đánh đổi là trace không có full prompt để debug, nhưng khi cần vẫn xem được nội dung prompt qua link prompt version trên generation.
- **Một lỗi/blocker đã gặp:** trong `data/logs.jsonl` có 9 request `qa` với `latency_ms` 1269–2222 ms, trong khi bình thường chỉ khoảng 152 ms. Mỗi lần khởi động API, request đầu tiên luôn chậm như vậy. Việc này làm P95 toàn file thành 2222 ms và dễ bị nhầm với sự cố `rag_slow`.
- **Cách tìm nguyên nhân và xử lý:** tôi so khớp các request chậm với trace cùng `correlation_id`. Ví dụ trace `63784068630f383a9f19a3859504cc5f` (`req-c7c1271d`): `retrieval` 0.002 s + `generation` 0.152 s, nhưng `lab-agent-run` tới 2.217 s, tức khoảng 2 s không thuộc span con nào. Khoảng thời gian thiếu là lúc gọi `resolve_prompt` → `client.get_prompt(...)` lấy prompt từ Langfuse lần đầu (cache rỗng), và bước này nằm trong khoảng đo `latency_ms`. Các request sau dùng cache (`cache_ttl_seconds=60`) nên nhanh lại. Tôi xử lý ở tầng phân tích: loại cold start khi báo P95 ổn định và khi điều tra CP3 thì so sánh cùng khung thời gian. Hướng sửa: prefetch prompt lúc startup trong `lifespan`, và tạo span riêng cho bước lấy prompt để trace thể hiện rõ. Cũng liên quan tới cache: sau khi rollback label `production`, SDK có thể vẫn trả version cũ tới khi hết TTL, nên tôi phải restart API để kiểm chứng rollback (mục 5).
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời *có vấn đề gì, từ khi nào, lớn cỡ nào*. Ở CP3, P95 tăng từ 179 lên 2652 ms trong 16:56:55–16:57:09 và chỉ ở feature `monitoring`. Logs trả lời *request cụ thể nào bị ảnh hưởng*: lọc `latency_ms > 2000` trong khung đó ra `req-2fe0a88d`. Traces trả lời *chậm ở bước nào trong request đó*: trace có cùng `correlation_id` cho thấy `retrieval` chiếm 2.5/2.65 s. Root cause chỉ được kết luận khi cả ba cùng chỉ về một chỗ. Nếu mở trace ngẫu nhiên thì dễ gặp trace cold start và kết luận sai.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt thay đổi hành vi giống như deploy code, nên cần version và label. Candidate v2 thêm một câu hướng dẫn làm `tokens_in` tăng từ 32 lên 43 với cùng input, tức cost/request tăng. Nếu không có `prompt_version` trong trace thì không biết regression đến từ prompt hay từ code. Rollback bằng label (`production` → v1) không cần deploy, trace sau đó xác nhận `prompt_version=1`. SLO và error budget quyết định khi nào phải dừng thay đổi để ưu tiên ổn định, còn token/cost cho biết chi phí của một thay đổi prompt trước khi nó thành hóa đơn.
- **Điều quan trọng nhất đã học:** một metric "đạt" chưa chắc đã an toàn. Sự cố CP3 làm người dùng chờ tới 13 s nhưng không làm error rate hay retrieval success đổi, và vẫn dưới ngưỡng SLO 3000 ms. Chọn đúng SLI (đo ở đâu, ngưỡng nào, theo từng bước) quan trọng hơn việc có nhiều dashboard.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) `HighLatencyP95` với ngưỡng 3000 ms không phát hiện được sự cố CP3; tôi mới đề xuất alert theo độ trễ retrieval, chưa triển khai. (2) Chưa sửa lỗi `/chat` async gọi code đồng bộ khiến request bị xếp hàng, và chưa prefetch prompt lúc startup. (3) `latency_ms` chỉ đo trong agent, không gồm thời gian chờ hàng đợi. (4) LLM là fake, nên token/cost/quality chỉ minh họa cách đo, không phản ánh chất lượng thật.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
