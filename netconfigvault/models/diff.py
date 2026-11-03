"""Data models for configuration comparison and semantic diffing."""

from dataclasses import field
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class DiffSection(BaseModel):
    """Represents a specific configuration block/section that changed."""
    section_name: str = Field(..., description="E.g. interface, routing, firewall, acl")
    added_count: int = Field(default=0)
    removed_count: int = Field(default=0)
    lines: List[str] = Field(default_factory=list)


class DiffResult(BaseModel):
    """Result of comparing two configuration versions."""
    hostname: str
    has_changes: bool
    added_lines: int = Field(default=0)
    removed_lines: int = Field(default=0)
    changed_sections: List[str] = Field(default_factory=list)
    unified_diff: str = Field(default="", description="Unified diff text")
    html_diff: Optional[str] = Field(default=None, description="Styled side-by-side HTML diff table")
    summary: str = Field(default="No changes detected")
    timestamp: datetime = Field(default_factory=datetime.now)
