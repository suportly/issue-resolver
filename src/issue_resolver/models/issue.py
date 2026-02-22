"""GitHub issue model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """A GitHub issue discovered through scanning."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_owner: str
    repo_name: str
    number: int
    title: str
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    url: str
    state: str = "open"
    has_assignees: bool = False
    has_linked_prs: bool = False
    language: str | None = None
    repo_stars: int | None = None
    created_at: datetime
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def full_repo(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"
