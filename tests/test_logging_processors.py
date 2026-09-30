from __future__ import annotations

import structlog

from app import logging_config


def test_scrub_runs_after_exception_formatting_and_before_writers() -> None:
    logging_config.configure_logging()
    processors = structlog.get_config()["processors"]
    scrub = processors.index(logging_config.scrub_event)
    exc = processors.index(structlog.processors.format_exc_info)
    writer = next(i for i, p in enumerate(processors) if isinstance(p, logging_config.JsonlFileProcessor))
    renderer = next(i for i, p in enumerate(processors) if isinstance(p, structlog.processors.JSONRenderer))

    assert exc < scrub < writer < renderer


def test_scrub_event_covers_nested_and_exception_text() -> None:
    event = {
        "event": "request_failed",
        "correlation_id": "req-12345678",
        "exception": "ValueError: bad email student@vinuni.edu.vn",
        "payload": {"detail": ["call 0901234567"]},
    }
    out = logging_config.scrub_event(None, "error", event)
    assert "student@" not in out["exception"]
    assert out["payload"]["detail"] == ["call [REDACTED_PHONE_VN]"]
    assert out["correlation_id"] == "req-12345678"
