from __future__ import annotations

from datetime import datetime, timezone

from scripts.build_dashboard import aggregate


def _rec(event: str, second: int, **fields) -> dict:
    ts = datetime(2026, 9, 30, 10, 0, second, tzinfo=timezone.utc)
    return {"event": event, "_ts": ts, **fields}


def test_aggregate_matches_dashboard_contract() -> None:
    records = [
        _rec("request_received", 1),
        _rec("response_sent", 2, latency_ms=100, ttft_ms=50, cost_usd=0.002, tokens_in=30, tokens_out=100,
             quality_score=0.9, tool_success=True),
        _rec("request_received", 3),
        _rec("request_failed", 4, error_type="RuntimeError", tool_success=False),
    ]
    end = datetime(2026, 9, 30, 10, 0, 59, tzinfo=timezone.utc)
    slots, _, totals = aggregate(records, end, minutes=60)

    assert len(slots) == 60
    assert totals["count"] == 2
    assert totals["error_rate_pct"] == 50.0
    assert totals["tool_success_rate_pct"] == 50.0
    assert totals["errors_by_type"] == {"RuntimeError": 1}
    assert totals["p95"] == 100.0
    assert totals["tokens_out"] == 100
    assert totals["quality_mean"] == 0.9


def test_aggregate_ignores_records_outside_time_range() -> None:
    old = {"event": "request_received", "_ts": datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)}
    end = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    _, _, totals = aggregate([old], end, minutes=60)
    assert totals["count"] == 0
