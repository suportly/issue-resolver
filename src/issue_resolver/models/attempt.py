"""Resolution attempt model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from issue_resolver.models.enums import AttemptStatus, OutcomeCategory


class Attempt(BaseModel):
    """A record of a resolution attempt."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str
    status: AttemptStatus = AttemptStatus.PENDING
    outcome: OutcomeCategory | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    workspace_path: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    branch_name: str | None = None
    num_turns: int | None = None
    model: str | None = None
    test_output: str | None = None
    diff_summary: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
