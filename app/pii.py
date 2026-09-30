from __future__ import annotations

import hashlib
import re

# Thứ tự quan trọng (dict giữ thứ tự chèn):
# - CCCD (12 số liền) che trước thẻ: nếu không, "CCCD + khoảng trắng + thẻ" bị regex thẻ
#   match nhầm "12 số CCCD + 4 số đầu thẻ", để lộ 12 số cuối của thẻ.
# - Thẻ che trước SĐT để pattern SĐT không cắt vụn một số thẻ.
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # Hộ chiếu Việt Nam: 1 chữ cái in hoa + 7 chữ số, ví dụ B1234567.
    "passport": r"\b[A-Z]\d{7}\b",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
