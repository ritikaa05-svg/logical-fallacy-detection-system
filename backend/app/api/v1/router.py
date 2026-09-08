"""
API v1 Router
Defines the /api/v1/analyze and /api/v1/health endpoints.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.config import settings
from backend.app.core.device_manager import device_manager
from backend.app.core.security import rate_limit_middleware, sanitize_input, validate_input_length
from backend.app.pipeline.orchestrator import pipeline_orchestrator
from backend.app.schemas.inference import InferenceRequest, InferenceResult
from backend.app.services.cache_service import cache_service
from backend.app.services.health_tracker import health_tracker

logger = logging.getLogger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/history", summary="Get logic health history")
async def get_logic_history():
    """Retrieve historical logic scores for health monitoring."""
    return health_tracker.get_history()


@router.post(
    "/analyze",
    response_model=InferenceResult,
    status_code=status.HTTP_200_OK,
    summary="Analyze text for logical fallacies",
    description="""
    Run the complete 4-stage LogiScan pipeline on the provided text.

    **Pipeline Stages:**
    1. **Gatekeeper**: Determines if the text contains a logical claim
    2. **Coarse Classification**: Identifies the broad fallacy category
    3. **Fine-Grained Classification**: Pinpoints specific fallacy types
    4. **Neuro-Symbolic Analysis**: Formal validation (Z3) + human-readable correction

    **Performance:**
    - Cached responses: < 100ms
    - Fresh analysis (GPU): < 1.5s
    - Fresh analysis (CPU): < 3.0s

    **Rate Limit:** 60 requests per minute per IP address.
    """,
    dependencies=[Depends(rate_limit_middleware)],
)
async def analyze_text(
    request: InferenceRequest,
    req: Request,
    response: Response,
) -> InferenceResult:
    """
    Main inference endpoint for logical fallacy detection.

    Args:
        request: InferenceRequest with text to analyze
        req: FastAPI Request object (for middleware state)

    Returns:
        Complete InferenceResult with fallacy analysis
    """
    # Step 1: Sanitize input
    try:
        sanitized_text = sanitize_input(request.text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Input sanitization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input validation failed: {str(e)}",
        )

    # Step 2: Validate length
    try:
        validate_input_length(sanitized_text)
    except HTTPException:
        raise

    # Step 3: Run pipeline
    logger.info(
        f"Analyze request: text_len={len(sanitized_text)} chars, "
        f"skip_cache={request.skip_cache}, "
        f"ip={req.client.host if req.client else 'unknown'}"
    )

    try:
        result = await pipeline_orchestrator.analyze(
            text=sanitized_text,
            skip_cache=request.skip_cache,
            history=request.history,
            include_explanations=request.include_explanations,
            localize=request.localize,
            fast_track=request.fast_track,
            analysis_id=getattr(req.state, "request_id", None),
        )

        logger.info(
            f"Analysis complete: logic_score={result.logic_score:.2f}, "
            f"cached={result.cached}, latency={result.total_latency_ms:.1f}ms"
        )

        response.headers["X-LogiScan-Degradation"] = str(result.degradation_tier)

        return result

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Returns system health information including device status and cache connectivity.",
)
async def health_check() -> dict:
    """
    Comprehensive health check for monitoring.
    """
    cache_health = await cache_service.health_check()
    from backend.app.services.unified_classifier import unified_classifier

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "classifier_mode": "Mock" if unified_classifier.mock_mode else "Real",
        "device": device_manager.device_info,
        "cache": cache_health,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes/container orchestration.",
)
async def liveness_check() -> dict:
    """Minimal liveness probe that always returns healthy if the server is running."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Readiness check that validates cache connectivity.",
)
async def readiness_check() -> dict:
    """
    Readiness probe for Kubernetes.
    Returns 503 if critical dependencies are unavailable.
    """
    cache_available = cache_service.is_available

    # Note: Cache unavailability is non-fatal (pipeline works without it)
    # Only return not-ready for truly critical failures

    return {
        "status": "ready",
        "cache_available": cache_available,
    }


@router.get(
    "/models/status",
    status_code=status.HTTP_200_OK,
    summary="Model status",
    description="Returns which models are currently loaded in memory.",
)
async def model_status() -> dict:
    """Return the status of cached models in the lifecycle manager."""
    from backend.app.core.lifecycle import lifecycle_manager
    from backend.app.services.unified_classifier import unified_classifier

    return {
        "classifier_mode": "Mock" if unified_classifier.mock_mode else "Real",
        "cached_models": lifecycle_manager.cached_models,
        "model_count": lifecycle_manager.model_count,
        "device": device_manager.device_info,
    }
