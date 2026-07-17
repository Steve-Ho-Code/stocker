"""Safe logging shared by price providers."""

import logging

import httpx


def log_provider_failure(
    logger: logging.Logger,
    provider: str,
    exc: Exception,
) -> None:
    """Log a provider failure without rendering the exception."""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = getattr(exc.response, "status_code", None)
        logger.error(
            "Price provider HTTP request failed: provider=%s status=%s.",
            provider,
            status_code,
            extra={"provider": provider, "http_status": status_code},
        )
        return

    error_type = type(exc).__name__
    if isinstance(exc, httpx.RequestError):
        message = "Price provider request failed: provider=%s error_type=%s."
    else:
        message = (
            "Unexpected price provider failure: "
            "provider=%s error_type=%s."
        )
    logger.error(
        message,
        provider,
        error_type,
        extra={"provider": provider, "error_type": error_type},
    )
