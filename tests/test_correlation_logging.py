from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app

PII_MESSAGE = (
    "Contact student@vinuni.edu.vn or 0901234567, CCCD 001203004567, "
    "card 4111 1111 1111 1111"
)


def _post(payload: dict, headers: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json=payload, headers=headers or {})

    return asyncio.run(send())


def _payload(user: str, message: str = "Explain monitoring") -> dict:
    return {"user_id": user, "session_id": f"s-{user}", "feature": "qa", "message": message}


def test_generates_correlation_id_and_returns_headers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    response = _post(_payload("u1"))

    cid = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", cid)
    assert response.json()["correlation_id"] == cid
    assert int(response.headers["x-response-time-ms"]) >= 0


def test_reuses_incoming_request_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    response = _post(_payload("u1"), headers={"x-request-id": "req-abcdef12"})
    assert response.headers["x-request-id"] == "req-abcdef12"


def test_logs_are_enriched_scrubbed_and_not_leaking_between_requests(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    first = _post(_payload("u1", PII_MESSAGE)).headers["x-request-id"]
    second = _post(_payload("u2")).headers["x-request-id"]
    assert first != second

    raw = log_path.read_text(encoding="utf-8")
    for secret in ("student@vinuni.edu.vn", "0901234567", "001203004567", "4111 1111 1111 1111"):
        assert secret not in raw

    records = [json.loads(line) for line in raw.splitlines()]
    api_records = [r for r in records if r.get("service") == "api"]
    for rec in api_records:
        for field in ("correlation_id", "user_id_hash", "session_id", "feature", "model", "env"):
            assert field in rec
    by_cid = {r["correlation_id"]: r for r in api_records if r["event"] == "request_received"}
    assert by_cid[first]["session_id"] == "s-u1"
    assert by_cid[second]["session_id"] == "s-u2"
