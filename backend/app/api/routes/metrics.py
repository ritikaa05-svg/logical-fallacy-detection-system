import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from backend.app.core.telemetry import metrics

logger = logging.getLogger(__name__)

ALLOWED_IPS = ["127.", "10.", "172.16.", "192.168.", "::1"]


def metrics_auth(request: Request):
    client_ip = request.client.host if request.client else ""
    if not any(client_ip.startswith(prefix) for prefix in ALLOWED_IPS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False, dependencies=[Depends(metrics_auth)])
async def metrics_endpoint():
    raw = metrics.generate()
    return Response(
        content=raw.decode("utf-8"),
        media_type="text/plain; charset=utf-8",
    )
