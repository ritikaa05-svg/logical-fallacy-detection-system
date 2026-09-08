"""
Contradiction schemas — Phase 6, Deliverable B2.
Defines ContradictionMatch and CrossSegmentContradictions Pydantic models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContradictionMatch(BaseModel):
    """A single detected contradiction between two document segments."""

    segment_a_index: int = Field(description="0-based index of the first segment.")
    segment_b_index: int = Field(description="0-based index of the second segment.")
    segment_a_page: int | None = Field(
        default=None,
        description="1-based page number of segment A, if available.",
    )
    segment_b_page: int | None = Field(
        default=None,
        description="1-based page number of segment B, if available.",
    )
    type: str = Field(
        description="Detection strategy: 'lexical', 'z3', or 'semantic'.",
    )
    description: str = Field(
        description=(
            "Human-readable description of the contradiction, e.g. "
            "'Page 1 claims tax cuts increase revenue but Page 3 claims they reduce income.'"
        )
    )
    severity: str = Field(
        description="Severity level: 'minor', 'moderate', or 'critical'.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this contradiction detection.",
    )


class CrossSegmentContradictions(BaseModel):
    """Aggregated result of cross-segment contradiction analysis."""

    contradictions: list[ContradictionMatch] = Field(
        default_factory=list,
        description="List of detected contradictions.",
    )
    total_pairs_checked: int = Field(
        default=0,
        description="Total number of segment pairs that were compared.",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken for cross-segment analysis in milliseconds.",
    )
