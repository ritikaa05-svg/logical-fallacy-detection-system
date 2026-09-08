"""
Phase 9.4: Symbolic Trace Router

Serves persisted symbolic trace trees for the Researcher's Dashboard.
GET /api/v1/traces/{analysis_id} -> TraceResponse {analysis_id, trace_tree}
"""

import logging

from fastapi import APIRouter, HTTPException, status

from backend.app.services.trace_store import trace_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["traces"])


@router.get(
    "/traces/{analysis_id}",
    summary="Get symbolic trace for an analysis",
    description="""
    Returns the persisted symbolic trace tree for a prior /analyze call.

    The tree visualizes the neuro-symbolic pipeline: gatekeeper salience,
    structural argument extraction, coarse/fine classification with confidence
    scores, and the Z3 formal check (SMT script, model output, satisfiability).

    Traces are retained for the most recent analyses (configurable via
    TRACE_MAX_FILES). Returns 404 if the analysis is unknown or expired.
    """,
)
async def get_trace(analysis_id: str) -> dict:
    trace = trace_store.get(analysis_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trace found for analysis '{analysis_id}'. "
            "Traces are kept only for recent analyses (TRACE_MAX_FILES).",
        )
    return {
        "analysis_id": trace.get("analysis_id", analysis_id),
        "trace_tree": trace.get("trace_tree"),
    }
