import io
import json
import logging
import sys

import pytest

from src.logging_config import (
    REDACTED,
    RedactingJsonFormatter,
    configure_logging,
    redact_credentials,
)


@pytest.mark.parametrize(
    "parameter_name",
    ["token", "api_key", "api-key", "apikey", "access_token", "API_KEY"],
)
def test_redact_credentials_masks_sensitive_parameters(parameter_name):
    secret = f"secret-for-{parameter_name}"
    message = (
        "request failed: https://example.test/quote?safe=value"
        f"&{parameter_name}={secret}&other=ok"
    )

    redacted = redact_credentials(message)

    assert secret not in redacted
    assert f"{parameter_name}={REDACTED}" in redacted
    assert "safe=value" in redacted
    assert "other=ok" in redacted


def test_redact_credentials_masks_configured_secrets_outside_query_strings():
    bot_token = "123456:telegram-secret"
    message = f"request failed: https://api.telegram.org/bot{bot_token}/getMe"

    redacted = redact_credentials(message, sensitive_values=(bot_token,))

    assert bot_token not in redacted
    assert f"bot{REDACTED}/getMe" in redacted


def test_redacting_json_formatter_masks_message_args_and_exception_text():
    secret = "finnhub-formatter-secret"
    url = f"https://finnhub.io/api/v1/quote?symbol=VOO&token={secret}"
    formatter = RedactingJsonFormatter(sensitive_values=(secret,))

    try:
        raise RuntimeError(f"upstream failure for {url}")
    except RuntimeError:
        record = logging.LogRecord(
            name="test.redaction",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="request failed: %s",
            args=(url,),
            exc_info=__import__("sys").exc_info(),
        )

    rendered = formatter.format(record)
    payload = json.loads(rendered)

    assert secret not in rendered
    assert REDACTED in rendered
    assert payload["message"].startswith("request failed:")


def test_configure_logging_redacts_propagated_child_logger_records(
    monkeypatch,
):
    secret = "root-handler-secret"
    url = f"https://finnhub.io/api/v1/quote?token={secret}"
    stream = io.StringIO()
    root_logger = logging.getLogger()
    child_logger = logging.getLogger("src.providers.test_redaction")
    previous_root_handlers = root_logger.handlers[:]
    previous_root_level = root_logger.level
    previous_child_handlers = child_logger.handlers[:]
    previous_child_level = child_logger.level
    previous_child_propagate = child_logger.propagate

    try:
        monkeypatch.setattr(sys, "stdout", stream)
        configure_logging(
            level=logging.INFO,
            sensitive_values=(secret,),
        )
        child_logger.handlers.clear()
        child_logger.setLevel(logging.NOTSET)
        child_logger.propagate = True

        child_logger.error(
            "Price provider request failed: %s",
            url,
            extra={"provider": "finnhub", "http_status": 502},
        )
    finally:
        root_logger.handlers[:] = previous_root_handlers
        root_logger.setLevel(previous_root_level)
        child_logger.handlers[:] = previous_child_handlers
        child_logger.setLevel(previous_child_level)
        child_logger.propagate = previous_child_propagate

    rendered = stream.getvalue()
    payload = json.loads(rendered)
    assert secret not in rendered
    assert REDACTED in rendered
    assert payload["provider"] == "finnhub"
    assert payload["http_status"] == 502


def test_configure_logging_writes_redacted_rotating_local_files(tmp_path):
    secret = "local-file-secret"
    log_path = tmp_path / "nested" / "stocker.log"
    root_logger = logging.getLogger()
    child_logger = logging.getLogger("src.local_file_test")
    previous_root_handlers = root_logger.handlers[:]
    previous_root_level = root_logger.level
    previous_child_handlers = child_logger.handlers[:]
    previous_child_level = child_logger.level
    previous_child_propagate = child_logger.propagate

    try:
        configure_logging(
            level=logging.INFO,
            sensitive_values=(secret,),
            stream=io.StringIO(),
            file_path=log_path,
            file_max_bytes=180,
            file_backup_count=2,
        )
        child_logger.handlers.clear()
        child_logger.setLevel(logging.NOTSET)
        child_logger.propagate = True

        for index in range(10):
            child_logger.info(
                "Local log entry %s contains token=%s",
                index,
                secret,
            )

        installed_handlers = root_logger.handlers[:]
        for handler in installed_handlers:
            handler.flush()
            handler.close()
    finally:
        root_logger.handlers[:] = previous_root_handlers
        root_logger.setLevel(previous_root_level)
        child_logger.handlers[:] = previous_child_handlers
        child_logger.setLevel(previous_child_level)
        child_logger.propagate = previous_child_propagate

    log_files = sorted(log_path.parent.glob("stocker.log*"))
    assert log_path in log_files
    assert len(log_files) > 1

    rendered = "".join(
        log_file.read_text(encoding="utf-8") for log_file in log_files
    )
    assert secret not in rendered
    assert REDACTED in rendered
    for line in rendered.splitlines():
        json.loads(line)
