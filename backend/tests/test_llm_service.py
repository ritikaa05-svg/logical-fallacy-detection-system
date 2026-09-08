"""Unit tests for LLMSynthesisService tiered generation and load fallbacks."""

import pytest
from unittest.mock import MagicMock, PropertyMock, patch

from backend.app.config import settings
from backend.app.core.device_manager import ExecutionTarget, device_manager
from backend.app.services.llm_service import LLMSynthesisService


@pytest.fixture
def service():
    return LLMSynthesisService()


@pytest.mark.asyncio
async def test_api_path_skipped_when_local_path_is_set(service):
    """Regression: STAGE4_IS_LOCAL_PATH=True must not send the local filesystem
    path as the HF API model id (invalid URL). The API tier is skipped entirely."""
    with patch("backend.app.services.llm_service.device_manager.get_stage_target", return_value=ExecutionTarget.HUGGINGFACE_API), \
         patch.object(type(device_manager), "use_api_fallback", new_callable=PropertyMock, return_value=True), \
         patch.object(settings, "STAGE4_IS_LOCAL_PATH", True), \
         patch.object(settings, "DISABLE_API_FALLBACK", False), \
         patch("backend.app.services.llm_service.aiohttp.ClientSession") as mock_session, \
         patch("backend.app.services.llm_service.lifecycle_manager.get_or_load", side_effect=RuntimeError("no local model")):
        with pytest.raises(RuntimeError):
            await service._generate_with_fallback("test prompt", max_new_tokens=10)
        mock_session.assert_not_called()


@pytest.mark.asyncio
async def test_api_path_used_when_remote_model_configured(service):
    """With STAGE4_IS_LOCAL_PATH=False, the API tier runs against the HF model id."""

    class FakeResponse:
        status = 200

        async def json(self):
            return [{"generated_text": "test promptanswer"}]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeSession:
        def __init__(self):
            self.last_url = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        # Not async: the caller uses `async with post(...)`, where post(...) must
        # return the async context manager (FakeResponse) directly.
        def post(self, url, **kwargs):
            self.last_url = url
            return FakeResponse()

    fake_session = FakeSession()

    with patch("backend.app.services.llm_service.device_manager.get_stage_target", return_value=ExecutionTarget.HUGGINGFACE_API), \
         patch.object(type(device_manager), "use_api_fallback", new_callable=PropertyMock, return_value=False), \
         patch.object(settings, "STAGE4_IS_LOCAL_PATH", False), \
         patch.object(settings, "DISABLE_API_FALLBACK", False), \
         patch.object(settings, "STAGE4_SYNTHESIS_MODEL", "facebook/opt-125m"), \
         patch.object(settings, "HUGGINGFACE_API_URL", "https://api-inference.huggingface.co/models"), \
         patch.object(settings, "HUGGINGFACE_API_TOKEN", "hf_test"), \
         patch("backend.app.services.llm_service.aiohttp.ClientSession", return_value=fake_session):
        result = await service._generate_with_fallback("test prompt", max_new_tokens=10)
        assert result == "answer"
        assert "facebook/opt-125m" in fake_session.last_url


def test_quantized_load_falls_back_to_standard_cpu(service):
    """Regression: a failing 4-bit/quantized load must actually fall back to a
    plain fp32 CPU load instead of logging 'falling back' and re-raising."""
    first_model = MagicMock()
    fallback_model = MagicMock()
    with patch.object(settings, "STAGE4_IS_LOCAL_PATH", True), \
         patch.object(settings, "STAGE4_SYNTHESIS_MODEL", "/fake/model/path"), \
         patch("backend.app.services.llm_service.torch.cuda.is_available", return_value=False), \
         patch("backend.app.services.llm_service.device_manager.get_torch_device", return_value=MagicMock(type="cpu")), \
         patch("transformers.AutoTokenizer.from_pretrained", return_value=MagicMock()), \
         patch("transformers.AutoModelForCausalLM.from_pretrained", side_effect=[RuntimeError("OOM"), fallback_model]) as mock_load:
        result = service._load()
        assert mock_load.call_count == 2
        assert service._model is fallback_model
        assert result is service


def test_load_reraises_when_fallback_also_fails(service):
    with patch.object(settings, "STAGE4_IS_LOCAL_PATH", True), \
         patch.object(settings, "STAGE4_SYNTHESIS_MODEL", "/fake/model/path"), \
         patch("backend.app.services.llm_service.torch.cuda.is_available", return_value=False), \
         patch("backend.app.services.llm_service.device_manager.get_torch_device", return_value=MagicMock(type="cpu")), \
         patch("transformers.AutoTokenizer.from_pretrained", return_value=MagicMock()), \
         patch("transformers.AutoModelForCausalLM.from_pretrained", side_effect=[RuntimeError("OOM"), RuntimeError("disk full")]) as mock_load:
        with pytest.raises(RuntimeError, match="disk full"):
            service._load()
        assert mock_load.call_count == 2
        assert service._model is None
