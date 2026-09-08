"""
Hardware Detection and Execution Routing Engine
Singleton pattern with thread-safe initialization and memory monitoring.
"""

import gc
import logging
import platform
import threading
from enum import Enum, auto
from typing import Optional

import torch
import torch.cuda

from backend.app.config import settings

logger = logging.getLogger(__name__)


class ExecutionTarget(Enum):
    """Enumeration of possible execution backends for model inference."""

    ONNX_CPU = auto()  # Stage 1 default: ONNX Runtime on CPU
    PYTORCH_CUDA = auto()  # Local NVIDIA GPU with sufficient VRAM
    PYTORCH_MPS = auto()  # Apple Silicon GPU via Metal Performance Shaders
    HUGGINGFACE_API = auto()  # Remote inference via Hugging Face API


class DeviceManager:
    """
    Thread-safe singleton for hardware detection and execution routing.

    Detection Hierarchy:
    1. Apple MPS (Metal Performance Shaders)
    2. NVIDIA CUDA with VRAM >= 4GB
    3. CPU-only with API fallback for large models

    Usage:
        dm = DeviceManager()
        target = dm.get_stage_target(stage=3)
    """

    _instance: Optional["DeviceManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "DeviceManager":
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.device_str: str = "cpu"
        self.exec_target: ExecutionTarget = ExecutionTarget.ONNX_CPU
        self._use_api_fallback: bool = False
        self._api_fallback_lock: threading.Lock = threading.Lock()
        self.use_4bit_cuda: bool = False
        self.vram_gb: float = 0.0
        self.cuda_available: bool = False
        self.mps_available: bool = False

        self._detect_hardware()
        logger.info(
            f"DeviceManager initialized: device={self.device_str}, "
            f"api_fallback={self.use_api_fallback}, vram={self.vram_gb:.1f}GB"
        )

    def _detect_hardware(self) -> None:
        """Detect available hardware and configure execution strategy."""

        # Tier 1: Apple Silicon MPS
        if platform.system() == "Darwin" and torch.backends.mps.is_available():
            self.device_str = "mps"
            self.mps_available = True
            self.exec_target = ExecutionTarget.PYTORCH_MPS
            # MPS has no direct VRAM query; assume sufficient for 4-bit models
            self.vram_gb = 8.0  # Conservative estimate for Apple Silicon
            logger.info("Apple MPS backend selected for PyTorch models.")
            return

        # Tier 2: NVIDIA CUDA
        if torch.cuda.is_available():
            self.cuda_available = True
            device_props = torch.cuda.get_device_properties(0)
            self.vram_gb = device_props.total_memory / (1024**3)

            if self.vram_gb >= 6.0:
                # Full-size GPU: use full-precision/local CUDA
                self.device_str = "cuda"
                self.exec_target = ExecutionTarget.PYTORCH_CUDA
                self.use_4bit_cuda = False
                self._use_api_fallback = False
                logger.info(f"CUDA backend selected (VRAM: {self.vram_gb:.1f} GB). Using native CUDA execution.")
            elif self.vram_gb >= 2.0:
                # Low-but-usable GPU: enable 4-bit CUDA for stages 2-4
                self.device_str = "cuda"
                self.exec_target = ExecutionTarget.PYTORCH_CUDA
                self.use_4bit_cuda = True
                # Prefer local 4-bit CUDA over API fallback for better latency
                self._use_api_fallback = False
                logger.info(
                    f"CUDA GPU with limited VRAM detected ({self.vram_gb:.1f} GB). "
                    "Enabling 4-bit CUDA for stages 2-4. Stage 1 remains ONNX CPU."
                )
            else:
                # Very small GPUs: fall back to API for heavy stages
                self.device_str = "cuda"
                self.use_4bit_cuda = False
                self._use_api_fallback = True
                # If no HF token is configured, API fallback is pointless
                if not settings.HUGGINGFACE_API_TOKEN:
                    self._use_api_fallback = False
                    logger.info("No HuggingFace API token configured. API fallback disabled.")
                # Allow user to force-disable API fallback via env var
                if settings.DISABLE_API_FALLBACK:
                    self._use_api_fallback = False
                    logger.info("API fallback disabled by DISABLE_API_FALLBACK setting. Using local models only.")
                logger.warning(
                    f"CUDA GPU has very limited VRAM ({self.vram_gb:.1f} GB < 2.0 GB). "
                    "Stages 2-4 will use Hugging Face API fallback or ONNX CPU as configured."
                )
            return

        # Tier 3: CPU-only
        self.device_str = "cpu"
        self.exec_target = ExecutionTarget.ONNX_CPU
        self._use_api_fallback = True
        # Allow user to force-disable API fallback via env var
        if settings.DISABLE_API_FALLBACK:
            self._use_api_fallback = False
            logger.info("API fallback disabled by DISABLE_API_FALLBACK setting. Using local models only.")
        logger.info("No GPU detected. CPU-only mode with API fallback for large models.")

    def get_stage_target(self, stage: int) -> ExecutionTarget:
        """
        Determine the execution target for a specific pipeline stage.

        Args:
            stage: Pipeline stage number (1-4)

        Returns:
            ExecutionTarget enum value for the stage
        """
        if stage == 1:
            # Stage 1 is always ONNX CPU for guaranteed low latency
            return ExecutionTarget.ONNX_CPU

        if stage in (2, 3, 4):
            # If a low-VRAM GPU supports 4-bit CUDA, prefer local CUDA execution for heavy stages
            if self.use_4bit_cuda:
                return self.exec_target
            if self.use_api_fallback:
                return ExecutionTarget.HUGGINGFACE_API
            return self.exec_target

        raise ValueError(f"Invalid pipeline stage: {stage}. Must be 1-4.")

    def get_torch_device(self) -> torch.device:
        """Get the appropriate PyTorch device for tensor operations."""
        if self.exec_target == ExecutionTarget.PYTORCH_CUDA:
            return torch.device("cuda:0")
        elif self.exec_target == ExecutionTarget.PYTORCH_MPS:
            return torch.device("mps")
        return torch.device("cpu")

    @staticmethod
    def cleanup_memory() -> None:
        """
        Aggressively free GPU/CPU memory.
        Should be called after large model evictions or on OOM errors.
        """
        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        if platform.system() == "Darwin" and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except AttributeError:
                # Older PyTorch versions may not have this method
                pass

        logger.debug("Memory cleanup completed across all devices.")

    def cuda_healthy(self) -> bool:
        try:
            t = torch.tensor([1.0]).cuda() + 1
            del t
            return True
        except Exception:
            return False

    def reset_cuda(self) -> bool:
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        if torch.cuda.is_available():
            try:
                device_props = torch.cuda.get_device_properties(0)
                self.vram_gb = device_props.total_memory / (1024**3)
                self.cuda_available = True
            except Exception:
                self.cuda_available = False
        else:
            self.cuda_available = False
        logger.info(f"CUDA reset completed. Available={self.cuda_available}, VRAM={self.vram_gb:.1f}GB")
        return self.cuda_available

    @property
    def use_api_fallback(self) -> bool:
        with self._api_fallback_lock:
            return self._use_api_fallback

    def set_api_fallback(self, value: bool) -> None:
        with self._api_fallback_lock:
            self._use_api_fallback = value

    @property
    def device_info(self) -> dict:
        """Return a dictionary with device information for health checks."""
        return {
            "device_string": self.device_str,
            "execution_target": self.exec_target.name,
            "api_fallback": self.use_api_fallback,
            "use_4bit_cuda": self.use_4bit_cuda,
            "vram_gb": round(self.vram_gb, 1),
            "cuda_available": self.cuda_available,
            "mps_available": self.mps_available,
        }


# Global singleton instance
device_manager = DeviceManager()
