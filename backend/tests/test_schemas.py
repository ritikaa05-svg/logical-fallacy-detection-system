"""Unit tests for Pydantic schema validators."""

import pytest

from backend.app.schemas.inference import Stage2Result


def test_stage2_result_accepts_informal_other():
    """Regression: 'Informal (Other)' must be a valid coarse category."""
    result = Stage2Result(coarse_category="Informal (Other)", confidence=0.8, latency_ms=1.0)
    assert result.coarse_category == "Informal (Other)"


def test_stage2_result_accepts_legacy_categories():
    for category in ["Formal", "Informal (Relevance)", "Informal (Ambiguity)", "Informal (Presumption)", "Non-Fallacious"]:
        result = Stage2Result(coarse_category=category, confidence=0.5, latency_ms=1.0)
        assert result.coarse_category == category


@pytest.mark.parametrize("bad", ["Unknown", "Informal", "", "formal"])
def test_stage2_result_rejects_unknown_categories(bad):
    with pytest.raises(ValueError):
        Stage2Result(coarse_category=bad, confidence=0.5, latency_ms=1.0)


def test_stage2_result_allows_none():
    result = Stage2Result(coarse_category=None, confidence=0.5, latency_ms=1.0)
    assert result.coarse_category is None
