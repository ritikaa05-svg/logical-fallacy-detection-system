import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_root_endpoints(client: AsyncClient):
    """Test root compatibility and health endpoints."""
    # Test Root: serves the React SPA when a build exists, else a JSON stub
    response = await client.get("/")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    if "html" in content_type:
        assert "html" in response.text.lower()
    else:
        assert "health" in response.json()

    # Test Root Liveness
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

    # Test Root Readiness
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "cache_available" in response.json()


@pytest.mark.asyncio
async def test_v1_endpoints(client: AsyncClient):
    """Test API v1 health endpoints."""
    # Test v1 Liveness
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

    # Test v1 Readiness
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "cache_available" in response.json()
