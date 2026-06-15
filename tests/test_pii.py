from app.pii import scrub_text, scrub_value


def test_scrub_email_credit_card_and_phone() -> None:
    value = "student@vinuni.edu.vn 4111 1111 1111 1111 0987654321"
    output = scrub_text(value)
    assert "student@" not in output
    assert "4111" not in output
    assert "0987654321" not in output
    assert "[REDACTED_EMAIL]" in output
    assert "[REDACTED_CREDIT_CARD]" in output
    assert "[REDACTED_PHONE]" in output


def test_scrub_nested_dict_list_and_raw_user_id() -> None:
    payload = {
        "user_id": "raw-user-123",
        "user": {
            "email": "student@example.com",
            "cards": ["4111111111111111"],
        },
    }
    output = scrub_value(payload)
    assert output["user_id"] == "[REDACTED_USER_ID]"
    assert output["user"]["email"] == "[REDACTED_EMAIL]"
    assert output["user"]["cards"] == ["[REDACTED_CREDIT_CARD]"]
