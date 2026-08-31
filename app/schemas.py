"""Pydantic models for the vehicle-info wrapper service."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class VehicleLookupRequest(BaseModel):
    license_plate: str = Field(
        ...,
        description="Vehicle license plate (7 or 8 digits).",
        examples=["12345678"],
    )

    @field_validator("license_plate")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        return value.strip()


class VehicleData(BaseModel):
    license_plate: str
    manufacturer: str
    model: str
    year: int
    color: str


# Normalized outcome types this service can return to a caller (e.g. a flow
# builder webhook node). Keeping these as an explicit closed set makes it
# easy for a no-code flow to branch on `status` instead of parsing HTTP
# status codes / heterogeneous error shapes from the upstream API.
LookupStatus = Literal["ok", "invalid_format", "not_found", "upstream_error"]


class VehicleLookupResponse(BaseModel):
    status: LookupStatus
    vehicle: Optional[VehicleData] = None
    message: str
    cached: bool = Field(
        default=False, description="True if this result was served from cache."
    )
