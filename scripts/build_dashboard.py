"""Dựng dashboard 6 panel từ data/logs.jsonl theo contract config/dashboard.yaml.

Không cần dependency ngoài: script sinh một file HTML tĩnh (SVG inline) có
meta refresh. Dùng --watch để tự build lại mỗi `refresh_seconds` giây.

    python scripts/build_dashboard.py            # build một lần
    python scripts/build_dashboard.py --watch    # build lại liên tục
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile

CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
DEFAULT_LOG = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_OUT = REPO_ROOT / "data" / "dashboard.html"

# Categorical slots theo thứ tự cố định (light, dark) — không xoay vòng.
SERIES = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500")]


# ---------------------------------------------------------------- dữ liệu


def load_records(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            rec["_ts"] = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        records.append(rec)
    return records


def minute_of(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


@dataclass
class Bucket:
    received: int = 0
    failed: int = 0
    latency: list[int] = field(default_factory=list)
    ttft: list[int] = field(default_factory=list)
    cost: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    quality: list[float] = field(default_factory=list)
    tool_ok: int = 0
    tool_total: int = 0


def aggregate(records: list[dict], end: datetime, minutes: int) -> tuple[list[datetime], dict[datetime, Bucket], dict]:
    start = minute_of(end) - timedelta(minutes=minutes - 1)
    slots = [start + timedelta(minutes=i) for i in range(minutes)]
    buckets = {s: Bucket() for s in slots}
    errors_by_type: dict[str, int] = {}
    for rec in records:
        slot = minute_of(rec["_ts"])
        if slot not in buckets:
            continue
        b = buckets[slot]
        event = rec.get("event")
        if event == "request_received":
            b.received += 1
        elif event == "request_failed":
            b.failed += 1
            et = rec.get("error_type") or "unknown"
            errors_by_type[et] = errors_by_type.get(et, 0) + 1
        elif event == "response_sent":
            b.latency.append(rec.get("latency_ms", 0))
            b.ttft.append(rec.get("ttft_ms", 0))
            b.cost += rec.get("cost_usd", 0.0)
            b.tokens_in += rec.get("tokens_in", 0)
            b.tokens_out += rec.get("tokens_out", 0)
            if rec.get("quality_score") is not None:
                b.quality.append(rec["quality_score"])
        if rec.get("tool_success") is not None:
            b.tool_total += 1
            b.tool_ok += 1 if rec["tool_success"] else 0

    all_b = list(buckets.values())
    lat = [v for b in all_b for v in b.latency]
    ttft = [v for b in all_b for v in b.ttft]
    received = sum(b.received for b in all_b)
    failed = sum(b.failed for b in all_b)
    tool_total = sum(b.tool_total for b in all_b)
    q = [v for b in all_b for v in b.quality]
    active = [b for b in all_b if b.received]
    totals = {
        "p50": percentile(lat, 50),
        "p95": percentile(lat, 95),
        "p99": percentile(lat, 99),
        "ttft_p95": percentile(ttft, 95),
        "count": received,
        "rate_per_minute": received / len(active) if active else 0.0,
        "error_rate_pct": failed / received * 100 if received else 0.0,
        "tool_success_rate_pct": sum(b.tool_ok for b in all_b) / tool_total * 100 if tool_total else None,
        "errors_by_type": errors_by_type,
        "cost_total": sum(b.cost for b in all_b),
        "tokens_in": sum(b.tokens_in for b in all_b),
        "tokens_out": sum(b.tokens_out for b in all_b),
        "quality_mean": mean(q) if q else None,
    }
    return slots, buckets, totals


# ---------------------------------------------------------------- vẽ


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "–"
    if unit == "ms":
        return f"{value:,.0f} ms"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "usd":
        return f"${value:.4f}"
    if unit == "tokens":
        return f"{value:,.0f}"
    if unit == "score_0_to_1":
        return f"{value:.2f}"
    if unit == "requests_per_minute":
        return f"{value:.1f} req/min"
    return f"{value}"


def line_chart(slots: list[datetime], series: list[tuple[str, list[float | None]]], threshold: float, unit: str) -> str:
    w, h, pl, pr, pt, pb = 560, 220, 64, 16, 12, 28
    values = [v for _, vals in series for v in vals if v is not None]
    ymax = max(values + [threshold]) * 1.15 or 1.0
    n = len(slots)

    def x(i: int) -> float:
        return pl + (w - pl - pr) * i / max(1, n - 1)

    def y(v: float) -> float:
        return pt + (h - pt - pb) * (1 - v / ymax)

    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart">']
    for k in range(5):
        v = ymax * k / 4
        parts.append(f'<line class="grid" x1="{pl}" x2="{w - pr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        parts.append(f'<text class="tick" x="{pl - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{html.escape(fmt(v, unit))}</text>')
    for i in range(0, n, 10):
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{h - 8}" text-anchor="middle">{slots[i]:%H:%M}</text>')
    parts.append(f'<text class="tick" x="{x(n - 1):.1f}" y="{h - 8}" text-anchor="end">{slots[-1]:%H:%M}</text>')
    ty = y(threshold)
    parts.append(f'<line class="threshold" x1="{pl}" x2="{w - pr}" y1="{ty:.1f}" y2="{ty:.1f}"/>')
    parts.append(f'<text class="threshold-label" x="{w - pr}" y="{ty - 5:.1f}" text-anchor="end">threshold {html.escape(fmt(threshold, unit))}</text>')

    for idx, (name, vals) in enumerate(series):
        cls = f"s{idx + 1}"
        segs, cur = [], []
        for i, v in enumerate(vals):
            if v is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append((i, v))
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) > 1:
                d = " ".join(f"{'M' if j == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for j, (i, v) in enumerate(seg))
                parts.append(f'<path class="line {cls}" d="{d}"/>')
        for i, v in enumerate(vals):
            if v is not None:
                tip = f"{name} · {slots[i]:%H:%M} UTC · {fmt(v, unit)}"
                parts.append(
                    f'<circle class="dot {cls}" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4"><title>{html.escape(tip)}</title></circle>'
                )
    parts.append("</svg>")
    return "".join(parts)


def legend(names: list[str]) -> str:
    if len(names) < 2:
        return ""
    items = "".join(f'<span class="key"><i class="sw s{i + 1}"></i>{html.escape(n)}</span>' for i, n in enumerate(names))
    return f'<div class="legend">{items}</div>'


def status_badge(ok: bool | None) -> str:
    if ok is None:
        return '<span class="badge none">– no data</span>'
    return '<span class="badge ok">✓ within threshold</span>' if ok else '<span class="badge bad">✕ breaching threshold</span>'


def check(value: float | None, op: str, limit: float) -> bool | None:
    if value is None:
        return None
    return value <= limit if op == "lte" else value >= limit


def cumulative(values: list[float], has_data: list[bool]) -> list[float | None]:
    out, run = [], 0.0
    for v, ok in zip(values, has_data):
        run += v
        out.append(run if ok else None)
    return out


def build_panels(cfg: dict, slots: list[datetime], buckets: dict[datetime, Bucket], t: dict) -> list[str]:
    panels = {p["id"]: p for p in cfg["panels"]}
    bs = [buckets[s] for s in slots]
    has_resp = [bool(b.latency) for b in bs]
    has_req = [bool(b.received) for b in bs]

    def pct(vals: list[int], p: int, ok: bool) -> float | None:
        return percentile(vals, p) if ok else None

    out = []

    def card(pid: str, headline: str, value_for_check: float | None, series, extra: str = "") -> None:
        p = panels[pid]
        th = p["threshold"]
        names = [n for n, _ in series]
        chart = line_chart(slots, series, th["value"], p["unit"])
        op_txt = "≤" if th["operator"] == "lte" else "≥"
        out.append(
            f'<section class="panel"><header><h2>{html.escape(p["title"])}</h2>'
            f'<span class="unit">unit: {html.escape(p["unit"])}</span></header>'
            f'<div class="headline">{headline}</div>'
            f'<div class="rule">threshold: {th["aggregation"]} {op_txt} {html.escape(fmt(th["value"], p["unit"]))} '
            f'{status_badge(check(value_for_check, th["operator"], th["value"]))}</div>'
            f"{legend(names)}{chart}{extra}</section>"
        )

    card(
        "latency",
        f'P50 <b>{fmt(t["p50"], "ms")}</b> · P95 <b>{fmt(t["p95"], "ms")}</b> · P99 <b>{fmt(t["p99"], "ms")}</b> · TTFT P95 <b>{fmt(t["ttft_p95"], "ms")}</b>',
        t["p95"] if t["count"] else None,
        [
            ("P50", [pct(b.latency, 50, ok) for b, ok in zip(bs, has_resp)]),
            ("P95", [pct(b.latency, 95, ok) for b, ok in zip(bs, has_resp)]),
            ("P99", [pct(b.latency, 99, ok) for b, ok in zip(bs, has_resp)]),
            ("TTFT P95", [pct(b.ttft, 95, ok) for b, ok in zip(bs, has_resp)]),
        ],
    )
    card(
        "traffic",
        f'Total <b>{t["count"]}</b> requests · avg <b>{fmt(t["rate_per_minute"], "requests_per_minute")}</b> (active minutes)',
        t["rate_per_minute"] if t["count"] else None,
        [("Requests/min", [float(b.received) if ok else None for b, ok in zip(bs, has_req)])],
    )
    breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(t["errors_by_type"].items())) or "no errors"
    card(
        "errors",
        f'Error rate <b>{fmt(t["error_rate_pct"], "percent")}</b> · Retrieval success <b>{fmt(t["tool_success_rate_pct"], "percent")}</b>',
        t["error_rate_pct"] if t["count"] else None,
        [
            ("Error rate %", [b.failed / b.received * 100 if b.received else None for b in bs]),
            ("Retrieval success %", [b.tool_ok / b.tool_total * 100 if b.tool_total else None for b in bs]),
        ],
        f'<p class="note">Error breakdown by type: {html.escape(breakdown)}</p>',
    )
    card(
        "cost",
        f'Total cost (window) <b>{fmt(t["cost_total"], "usd")}</b>',
        t["cost_total"] if t["count"] else None,
        [
            ("Cost per minute", [b.cost if ok else None for b, ok in zip(bs, has_resp)]),
            ("Cumulative cost", cumulative([b.cost for b in bs], has_resp)),
        ],
    )
    tokens_max = max(t["tokens_in"], t["tokens_out"])
    card(
        "tokens",
        f'Input <b>{fmt(t["tokens_in"], "tokens")}</b> · Output <b>{fmt(t["tokens_out"], "tokens")}</b> tokens',
        tokens_max if t["count"] else None,
        [
            ("Cumulative input tokens", cumulative([float(b.tokens_in) for b in bs], has_resp)),
            ("Cumulative output tokens", cumulative([float(b.tokens_out) for b in bs], has_resp)),
        ],
    )
    card(
        "quality",
        f'Mean quality proxy <b>{fmt(t["quality_mean"], "score_0_to_1")}</b>',
        t["quality_mean"],
        [("Mean quality", [mean(b.quality) if b.quality else None for b in bs])],
    )
    return out


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--border:rgba(11,11,11,.10);--crit:#d03b3b;--good:#006300;
--s1:%s;--s2:%s;--s3:%s;--s4:%s}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--border:rgba(255,255,255,.10);--good:#0ca30c;--s1:%s;--s2:%s;--s3:%s;--s4:%s}}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1240px;margin:0 auto;padding:20px 16px}
h1{font-size:20px;margin:0 0 4px}.meta{color:var(--ink2);margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.panel header{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
h2{font-size:15px;margin:0}.unit{color:var(--muted);font-size:12px}
.headline{margin:6px 0 2px;color:var(--ink2)}.headline b{color:var(--ink);font-variant-numeric:tabular-nums}
.rule{font-size:12px;color:var(--ink2)}.note{font-size:12px;color:var(--ink2);margin:4px 0 0}
.badge{margin-left:6px;font-weight:600}.badge.ok{color:var(--good)}.badge.bad{color:var(--crit)}.badge.none{color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:12px;color:var(--ink2)}
.key{display:inline-flex;align-items:center;gap:6px}.sw{width:10px;height:10px;border-radius:2px;display:inline-block}
.chart{width:100%%;height:auto;margin-top:6px}
.chart .grid{stroke:var(--grid);stroke-width:1}.tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.threshold{stroke:var(--crit);stroke-width:1.5;stroke-dasharray:6 4}.threshold-label{fill:var(--crit);font-size:11px}
.line{fill:none;stroke-width:2}.dot{stroke:var(--surface);stroke-width:2}
.s1{stroke:var(--s1)}.s2{stroke:var(--s2)}.s3{stroke:var(--s3)}.s4{stroke:var(--s4)}
circle.s1,.sw.s1{fill:var(--s1);background:var(--s1)}circle.s2,.sw.s2{fill:var(--s2);background:var(--s2)}
circle.s3,.sw.s3{fill:var(--s3);background:var(--s3)}circle.s4,.sw.s4{fill:var(--s4);background:var(--s4)}
circle.dot{stroke:var(--surface)}
""" % (*[c[0] for c in SERIES], *[c[1] for c in SERIES])


def render(cfg: dict, records: list[dict], end: datetime) -> str:
    minutes = cfg["time_range_minutes"]
    slots, buckets, totals = aggregate(records, end, minutes)
    panels = build_panels(cfg, slots, buckets, totals)
    start = slots[0]
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<meta http-equiv='refresh' content='{cfg['refresh_seconds']}'>"
        f"<title>{html.escape(cfg['title'])}</title><style>{CSS}</style></head><body><main>"
        f"<h1>{html.escape(cfg['title'])}</h1>"
        f"<div class='meta'>Time range: last {minutes} min ({start:%Y-%m-%d %H:%M} → {end:%H:%M} UTC) · "
        f"auto-refresh {cfg['refresh_seconds']}s · source: data/logs.jsonl · built {datetime.now(timezone.utc):%H:%M:%S} UTC</div>"
        f"<div class='grid'>{''.join(panels)}</div></main></body></html>"
    )


def build(log_path: Path, out_path: Path, end: datetime | None) -> None:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    records = load_records(log_path)
    end = end or datetime.now(timezone.utc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(cfg, records, end), encoding="utf-8")
    print(f"Dashboard: {out_path} ({len(records)} log records)")


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--end", help="Mốc cuối time range (ISO, UTC). Mặc định: hiện tại.")
    parser.add_argument("--watch", action="store_true", help="Build lại mỗi refresh_seconds giây.")
    args = parser.parse_args()
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else None

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    while True:
        build(args.log, args.out, end)
        if not args.watch:
            break
        time.sleep(cfg["refresh_seconds"])


if __name__ == "__main__":
    main()
