"""Issue solvability analysis model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from issue_resolver.models.enums import SolvabilityRating


class Analysis(BaseModel):
    """An AI-generated solvability assessment for an issue."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str
    rating: SolvabilityRating
    confidence: float
    complexity: str | None = None
    reasoning: str
    cost_usd: float | None = None
    model: str | None = None
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v

    @property
    def passes_threshold(self) -> bool:
        """Check if analysis passes the solvability gate (FR-003)."""
        return (
            self.rating in (SolvabilityRating.SOLVABLE, SolvabilityRating.LIKELY_SOLVABLE)
            and self.confidence >= 0.7
        )
