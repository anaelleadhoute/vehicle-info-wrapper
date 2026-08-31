"""Thin, resilient client for the upstream Insurance Company Stub API."""
import logging
import os
from typing import Literal

import httpx

logger = logging.getLogger("vehicle_info_wrapper.upstream")

UPSTREAM_BASE_URL = os.getenv(
    "UPSTREAM_BASE_URL",
    "https://insurance-webhook-945894769129.us-central1.run.app",
)
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "5"))
UPSTREAM_MAX_RETRIES = int(os.getenv("UPSTREAM_MAX_RETRIES", "2"))

UpstreamOutcome = Literal["ok", "invalid_format", "not_found", "upstream_error"]


class UpstreamResult:
    """Result of calling the upstream API, already classified."""

    def __init__(self, outcome: UpstreamOutcome, data: dict | None = None, detail: str = ""):
        self.outcome = outcome
        self.data = data
        self.detail = detail


async def fetch_vehicle_info(license_plate: str) -> UpstreamResult:
    """Call the upstream vehicle-info endpoint with a timeout and limited retries.

    Retries only on network errors / 5xx (transient failures). A 400 (bad
    format) or 404 (not found) is a legitimate business outcome, not a
    failure, so it is not retried.
    """
    url = f"{UPSTREAM_BASE_URL}/vehicle-info"
    last_error: str = ""

    for attempt in range(1, UPSTREAM_MAX_RETRIES + 2):  # e.g. 1 initial + N retries
        try:
            async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json={"license_plate": license_plate})
        except httpx.TimeoutException:
            last_error = "Upstream request timed out."
            logger.warning("Upstream timeout on attempt %d for plate=%s", attempt, license_plate)
            continue
        except httpx.HTTPError as exc:
            last_error = f"Upstream connection error: {exc}"
            logger.warning("Upstream connection error on attempt %d: %s", attempt, exc)
            continue

        if response.status_code == 200:
            payload = response.json()
            return UpstreamResult(outcome="ok", data=payload.get("data"))

        if response.status_code == 400:
            logger.info(
                "Upstream rejected plate=%s as invalid format: %s",
                license_plate,
                _extract_upstream_error(response),
            )
            return UpstreamResult(
                outcome="invalid_format",
                detail=f"License plate '{license_plate}' is not a valid format.",
            )

        if response.status_code == 404:
            logger.info(
                "Upstream reports plate=%s not found: %s",
                license_plate,
                _extract_upstream_error(response),
            )
            return UpstreamResult(
                outcome="not_found",
                detail=f"No vehicle found for license plate '{license_plate}'.",
            )

        # 5xx or anything unexpected: treat as transient, retry.
        last_error = f"Upstream returned unexpected status {response.status_code}."
        logger.warning(
            "Upstream unexpected status %d on attempt %d for plate=%s",
            response.status_code,
            attempt,
            license_plate,
        )

    return UpstreamResult(outcome="upstream_error", detail=last_error or "Upstream call failed.")


def _extract_upstream_error(response: httpx.Response) -> str:
    """Pull the (Hebrew) error message out of upstream's response, for logging.

    FastAPI's default HTTPException wraps whatever was raised under a
    top-level "detail" key, so a 400/404 body looks like:
      {"detail": {"success": false, "error": "..."}}
    not the flat {"success": false, "error": "..."} shape the OpenAPI spec's
    schema names implied. We don't surface this message to callers (see
    below) but it's useful in logs for debugging / verifying upstream
    behavior.
    """
    try:
        payload = response.json()
    except ValueError:
        return ""
    detail = payload.get("detail", payload)
    if isinstance(detail, dict):
        return detail.get("error", "")
    return str(detail)
