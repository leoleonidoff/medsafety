"""pydantic v2 request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DrugOut(BaseModel):
    id: Optional[int]
    rxnorm_cui: Optional[str]
    name: str
    generic_name: str
    drug_class: str


class DrugSearchOut(BaseModel):
    source: str
    results: list[DrugOut]


class PrescriptionIn(BaseModel):
    drug_id: Optional[int] = None
    rxnorm_cui: Optional[str] = None
    dosage_mg: float = Field(gt=0)
    schedule: str = Field(min_length=1, max_length=64)
    started_at: Optional[datetime] = None
    notes: Optional[str] = None


class PrescriptionPatch(BaseModel):
    dosage_mg: Optional[float] = Field(default=None, gt=0)
    schedule: Optional[str] = Field(default=None, min_length=1, max_length=64)
    notes: Optional[str] = None
    active: Optional[bool] = None
