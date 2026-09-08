"""
LogiScan — Main Application Entry Point
FastAPI application with lifecycle management for Redis connection.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.middleware import setup_exception_handlers, setup_middleware
from backend.app.api.routes.metrics import router as metrics_router
from backend.app.api.v1.debate_router import router as debate_router
from backend.app.api.v1.router import router as v1_router
from backend.app.api.v1.trace_router import router as trace_router
from backend.app.config import settings
from backend.app.core.device_manager import device_manager
from backend.app.core.logger import setup_logging
from backend.app.services.cache_service import cache_service

# Initialize structured logging
setup_logging(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup:
    - Connect to Redis cache
    - Log device configuration

    Shutdown:
    - Close Redis connection
    - Evict all models from memory
    """
    # --- Startup ---
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Device configuration: {device_manager.device_info}")

    # Connect to Redis
    await cache_service.connect()

    logger.info("Application startup complete. Ready to accept requests.")

    yield  # Application runs here

    # --- Shutdown ---
    logger.info("Shutting down application...")

    # Close Redis
    await cache_service.disconnect()

    # Evict models
    from backend.app.core.lifecycle import lifecycle_manager

    lifecycle_manager.evict_all()

    logger.info("Application shutdown complete.")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## LogiScan: Logical Fallacy Detection Engine

    A sovereign, resource-optimized system for detecting logical fallacies
    in natural language text using a 4-stage neuro-symbolic pipeline.

    ### Features
    - **4-Stage Pipeline**: Gatekeeper → Coarse Classification → Fine-Grained Detection → Neuro-Symbolic Analysis
    - **Hardware Adaptive**: Automatically detects GPU/CPU and adjusts inference strategy
    - **Caching**: Redis-backed result caching with 24-hour TTL
    - **Formal Verification**: Z3 SMT solver for formal deductive arguments
    - **Educational Corrections**: LLM-generated, respectful correction strategies

    ### Performance Targets
    - Cached responses: < 100ms
    - Fresh analysis (GPU): < 1.5s
    - Fresh analysis (CPU): < 3.0s
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Setup exception handlers
setup_exception_handlers(app)

# Include API routers
app.include_router(debate_router)
app.include_router(v1_router)
app.include_router(metrics_router)
app.include_router(trace_router)

# Phase 6: Document ingestion / analysis / reporting router
from backend.app.api.v1.document_router import router as document_router

app.include_router(document_router)


# Root-level health check endpoints for compatibility/legacy support.
# Registered BEFORE the SPA catch-all below so probes are never shadowed.
@app.get("/health/live", include_in_schema=False)
async def root_liveness_check():
    """Minimal liveness probe at the root level."""
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
async def root_readiness_check():
    """Readiness probe at the root level that checks cache status."""
    from backend.app.services.cache_service import cache_service

    return {
        "status": "ready",
        "cache_available": cache_service.is_available,
    }


# Serve React SPA build if available
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "../../frontend/dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str):
        if (
            path.startswith("api/")
            or path.startswith("docs")
            or path.startswith("redoc")
            or path.startswith("openapi")
            or path.startswith("health")
        ):
            return {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "health": "/api/v1/health",
            }
        file_path = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        spa_index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(spa_index):
            return FileResponse(spa_index)
        return {"error": "not found"}

    @app.get("/", include_in_schema=False)
    async def serve_spa_root():
        spa_index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(spa_index):
            return FileResponse(spa_index)
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }
else:
    # Root endpoint (fallback when no SPA build exists)
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect to API documentation."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }


@app.get("/health", include_in_schema=False)
async def root_health_check():
    """Health check at the root level."""
    from backend.app.api.v1.router import health_check

    return await health_check()


# For direct execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
