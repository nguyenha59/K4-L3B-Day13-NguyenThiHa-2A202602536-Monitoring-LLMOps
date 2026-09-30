"""Bước 2 của quy trình điều tra: lọc log bất thường để lấy correlation_id.

    python scripts/find_anomalies.py --latency-ms 3000
    python scripts/find_anomalies.py --since 2026-09-30T15:40 --feature monitoring
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio


def parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--latency-ms", type=int, default=3000, help="Ngưỡng latency coi là bất thường")
    parser.add_argument("--cost-usd", type=float, default=0.005, help="Ngưỡng cost/request coi là bất thường")
    parser.add_argument("--since", help="Chỉ xét log từ mốc này (ISO, UTC)")
    parser.add_argument("--feature", help="Chỉ xét một feature")
    args = parser.parse_args()

    since = parse_ts(args.since) if args.since else None
    hits = []
    for line in args.log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if since and parse_ts(rec["ts"]) < since:
            continue
        if args.feature and rec.get("feature") != args.feature:
            continue
        reasons = []
        if rec.get("event") == "request_failed":
            reasons.append(f"failed:{rec.get('error_type')}")
        if rec.get("event") == "response_sent":
            if rec.get("latency_ms", 0) > args.latency_ms:
                reasons.append(f"slow:{rec['latency_ms']}ms")
            if rec.get("cost_usd", 0) > args.cost_usd:
                reasons.append(f"costly:${rec['cost_usd']}")
        if reasons:
            hits.append((rec, reasons))

    print(f"Anomalous records: {len(hits)}")
    for rec, reasons in hits:
        print(
            f"{rec['ts']} | {rec.get('correlation_id')} | feature={rec.get('feature')} | "
            f"latency_ms={rec.get('latency_ms')} ttft_ms={rec.get('ttft_ms')} | {', '.join(reasons)}"
        )
        print("  " + json.dumps({k: v for k, v in rec.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
