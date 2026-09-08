import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.services.cache_service import cache_service


@pytest.fixture(scope="session")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def mock_cache(monkeypatch):
    """Ensure cache is not used during tests unless explicitly requested."""
    monkeypatch.setattr(cache_service, "_connected", False)
    monkeypatch.setattr(cache_service, "_redis", None)
