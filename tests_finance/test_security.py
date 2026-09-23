"""Validación de redacción de datos sensibles en logs (CF1-01)."""

import logging

from cuentafaro.security import (
    REDACTED,
    SensitiveDataFilter,
    install_log_redaction,
    redact_text,
    redact_value,
)


def test_redact_text_hides_bearer_token() -> None:
    text = "Authorization: Bearer ghx_ABCDEF123456 token values present"
    output = redact_text(text)
    assert "ghx_ABCDEF123456" not in output
    assert REDACTED in output


def test_redact_text_hides_key_value_secrets() -> None:
    text = 'api_key="super-secret-value" and password: hunter2'
    output = redact_text(text)
    assert "super-secret-value" not in output
    assert "hunter2" not in output
    assert output.count(REDACTED) >= 2


def test_redact_value_recurses_through_dict() -> None:
    payload = {"name": "demo", "token": "abc123", "nested": {"secret": "xyz", "amount": 100}}
    output = redact_value(payload)
    assert output["token"] == REDACTED
    assert output["nested"]["secret"] == REDACTED
    assert output["name"] == "demo"
    assert output["nested"]["amount"] == 100


def test_filter_redacts_log_records() -> None:
    logger = logging.getLogger("cuentafaro.test")
    original_handlers = list(logger.handlers)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    record = logger.makeRecord(
        logger.name, logging.INFO, __file__, 1, "api_key: leaked-value", (), None
    )
    assert SensitiveDataFilter().filter(record) is True
    assert "leaked-value" not in record.msg

    logger.handlers = original_handlers


def test_install_log_redaction_adds_filters_to_loggers() -> None:
    for name in ("uvicorn", "uvicorn.access", "cuentafaro", ""):
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
    install_log_redaction()
    for name in ("uvicorn", "uvicorn.access", "cuentafaro"):
        found = any(
            isinstance(item, SensitiveDataFilter)
            for handler in logging.getLogger(name).handlers
            for item in handler.filters
        )
        assert found, f"Filtro ausente en {name}"
