from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD cua toi la 001203004567")
    assert "001203004567" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_formats() -> None:
    for card in ("4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"):
        out = scrub_text(f"Card: {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport B1234567 het han")
    assert "B1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_keeps_normal_text() -> None:
    text = "Explain why metrics traces and logs work together"
    assert scrub_text(text) == text


def test_scrub_cccd_followed_by_card_does_not_leak_card_digits() -> None:
    out = scrub_text("079123456789 4111-1111-1111-1111")
    assert out == "[REDACTED_CCCD] [REDACTED_CREDIT_CARD]"


def test_scrub_card_with_mixed_separators() -> None:
    out = scrub_text("Card 4111 1111-1111 1111")
    assert out == "Card [REDACTED_CREDIT_CARD]"
