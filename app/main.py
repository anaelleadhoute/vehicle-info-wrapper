"""Vehicle-info wrapper service.

Wraps the upstream "Insurance Company Stub API" with:
  - server-side input validation before forwarding to upstream
  - a normalized response shape (single `status` field instead of a mix
    of HTTP codes / error shapes), which is much easier for a no-code
    conversation-flow builder to branch on
  - resilience: request timeout + limited retries on transient failures
  - a short-lived cache to avoid repeat calls for the same plate
  - structured logging
"""
import logging
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import cache
from app.schemas import VehicleData, VehicleLookupRequest, VehicleLookupResponse
from app.translate import translate_color, translate_manufacturer, translate_model
from app.upstream_client import fetch_vehicle_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("vehicle_info_wrapper")

app = FastAPI(
    title="Vehicle Info Wrapper API",
    description=(
        "Wraps the insurer's vehicle-info stub endpoint with validation, "
        "response normalization, and resilience, for consumption by the "
        "Insait/Encore Conversation Flow Agent."
    ),
    version="1.0.0",
)

PLATE_PATTERN = re.compile(r"^\d{7,8}$")


def _translate_vehicle_data(data: dict) -> dict:
    """Translate manufacturer/model/color from Hebrew to English.

    The upstream API returns these fields in Hebrew; this normalizes them
    to English so the conversation flow can present them to the user
    (and so flow logic doesn't need to handle Hebrew text). Cached
    alongside the rest of the vehicle data so the translation only
    happens once per plate.
    """
    return {
        **data,
        "manufacturer": translate_manufacturer(data["manufacturer"]),
        "model": translate_model(data["model"]),
        "color": translate_color(data["color"]),
    }


@app.get("/")
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/vehicle-info", response_model=VehicleLookupResponse)
async def vehicle_info(payload: VehicleLookupRequest) -> JSONResponse:
    plate = payload.license_plate

    # 1. Validate format ourselves before ever calling upstream -- avoids a
    #    wasted network call for input we already know is invalid.
    if not PLATE_PATTERN.match(plate):
        logger.info("Rejected invalid plate format: %r", plate)
        body = VehicleLookupResponse(
            status="invalid_format",
            message="License plate must be 7 or 8 digits.",
        )
        return JSONResponse(status_code=200, content=body.model_dump())

    # 2. Check cache.
    cached = cache.get(plate)
    if cached is not None:
        logger.info("Cache hit for plate=%s", plate)
        body = VehicleLookupResponse(
            status="ok",
            vehicle=VehicleData(**cached),
            message="Vehicle found.",
            cached=True,
        )
        return JSONResponse(status_code=200, content=body.model_dump())

    # 3. Call upstream with timeout + retry, already classified.
    result = await fetch_vehicle_info(plate)

    if result.outcome == "ok":
        translated = _translate_vehicle_data(result.data)
        cache.set(plate, translated)
        body = VehicleLookupResponse(
            status="ok",
            vehicle=VehicleData(**translated),
            message="Vehicle found.",
        )
        return JSONResponse(status_code=200, content=body.model_dump())

    if result.outcome == "not_found":
        body = VehicleLookupResponse(status="not_found", message=result.detail)
        return JSONResponse(status_code=200, content=body.model_dump())

    if result.outcome == "invalid_format":
        body = VehicleLookupResponse(status="invalid_format", message=result.detail)
        return JSONResponse(status_code=200, content=body.model_dump())

    # Genuine infrastructure failure (upstream unreachable / timed out after
    # retries). Unlike the business outcomes above, this *does* surface as a
    # non-200 -- the caller should treat it differently (e.g. escalate to a
    # human) rather than branch on it like a normal conversational outcome.
    logger.error("Upstream error for plate=%s: %s", plate, result.detail)
    body = VehicleLookupResponse(status="upstream_error", message=result.detail)
    return JSONResponse(status_code=502, content=body.model_dump())
