"""Typed request and response envelopes; strings preserve source precision."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# This adapter-owned scope is a security boundary, not a parser/schema copy.
# A future library release cannot expand MCP eligibility by adding fields.
PROJECT_FIELDS = frozenset({
    "Proj Title", "Current Plan", "Plan File", "Geom File", "Flow File",
    "Unsteady File", "Units",
})
PLAN_FIELDS = frozenset({
    "Plan Title", "Short Identifier", "Program Version", "Geom File", "Flow File",
    "Simulation Date", "Computation Interval", "Output Interval",
    "Instantaneous Interval", "Mapping Interval", "Run HTab", "Run UNet",
    "Run UNET", "Run WQNET", "Run WQNet", "Run Sediment", "Run Post Process", "Run PostProcess",
    "Friction Slope Method", "UNET D1 Cores", "UNET D2 Cores", "PS Cores",
    "UNET 1D Methodology", "UNET D2 Solver Type", "Description",
})


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    root: str = Field(min_length=1, max_length=2048, description="Configured allowed project root.")
    file: str = Field(min_length=1, max_length=512, description="Relative named project or plan file.")
    max_seconds: int = Field(default=10, ge=1, le=30, description="Killable worker time budget, including imports.")
    max_characters: int = Field(default=6000, ge=1024, le=16000)


class MetadataRequest(Request):
    fields: list[str] = Field(min_length=1, max_length=24)
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=40, ge=1, le=100)


class Source(BaseModel):
    root: str
    file: str
    size_bytes: int
    sha256: str
    encoding: str | None = None


class Record(BaseModel):
    field: str
    value: str
    occurrence: int


class Result(BaseModel):
    source: Source
    versions: dict[str, str]
    records: list[Record]
    total_records: int
    returned_records: int
    next_offset: int | None = None
    truncated: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    units: str | None = None
    time_basis: str = "Source strings; timezone and calendar basis are not inferred."
    scope: str = "Selected text metadata; no physical validity assessment."


class Information(BaseModel):
    server_version: str
    installed: dict[str, str]
    latest: dict[str, str | None]
    update_status: Literal["not_checked", "offline", "checked"]
    update_available: dict[str, bool]
    tools: list[str]
    metadata_api_available: bool
    allowed_roots: list[str]
    limits: dict[str, int]
    boundary: str
    documentation: str = "https://rascommander.info/ras/"
