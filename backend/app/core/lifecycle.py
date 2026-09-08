"""
Model Lifecycle Manager
Thread-safe singleton pattern with idle-time eviction for efficient memory usage.
Manages the lifecycle of all four pipeline stage models.
"""

import gc
import logging
import platform
import threading
import time
from typing import Any, Callable, Optional

import torch

logger = logging.getLogger(__name__)


class ModelLifecycleManager:
    """
    Singleton manager for model loading, caching, and eviction.

    Features:
    - Lazy loading: Models are loaded only on first use
    - Thread-safe access: Uses reentrant lock for concurrent requests
    - Idle eviction: Unloads models after configurable idle timeout
    - Memory cleanup: Triggers device-specific garbage collection

    Usage:
        manager = ModelLifecycleManager()
        model = manager.get_or_load("stage1", load_distilbert_onnx)
    """

    _instance: Optional["ModelLifecycleManager"] = None
    _lock: threading.RLock = threading.RLock()

    def __new__(cls) -> "ModelLifecycleManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, idle_timeout_sec: int = 3600):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self.idle_timeout_sec = idle_timeout_sec
        # Sequential residency: if False, allows multiple models to stay resident
        # Set to False by default if we have enough VRAM (> 2.5GB)
        self.low_memory_mode = False
        try:
            if torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb < 2.5:
                    self.low_memory_mode = True
                    logger.info(f"Low VRAM detected ({vram_gb:.1f}GB). Enabling low_memory_mode.")
        except Exception:
            pass

        self._models: dict[str, tuple[Any, float]] = {}  # {stage_name: (model, last_access)}
        self._eviction_interval = 300  # Check every 5 minutes
        self._start_eviction_timer()
        logger.info(
            f"ModelLifecycleManager initialized (timeout={idle_timeout_sec}s, low_memory={self.low_memory_mode})."
        )

    def get_or_load(self, stage_name: str, loader_fn: Callable[[], Any]) -> Any:
        """
        Thread-safe accessor that lazy-loads models and refreshes access timestamps.
        """
        with self._lock:
            now = time.time()

            # Return cached model if available
            if stage_name in self._models:
                model, _ = self._models[stage_name]
                self._models[stage_name] = (model, now)
                return model

            # LOW MEMORY: Evict others before loading new one
            if self.low_memory_mode:
                if self._models:
                    logger.info(f"Low memory mode: evicting existing models before loading {stage_name}.")
                    self.evict_all()
            else:
                # Selective eviction: if we are loading the heavy synthesis model, evict others
                if stage_name == "synthesis" and self._models:
                    logger.info("Loading heavy synthesis model: evicting classifier models to prevent OOM.")
                    self.evict_all()

            # Load model fresh
            logger.info(f"Loading model '{stage_name}' into memory...")
            try:
                model = loader_fn()
                self._models[stage_name] = (model, now)
                logger.info(f"Model '{stage_name}' loaded successfully.")

                # Perform memory cleanup after loading
                DeviceMemoryCleanup.run()

                return model
            except Exception as e:
                logger.error(f"Failed to load model '{stage_name}': {e}")
                DeviceMemoryCleanup.run()
                raise RuntimeError(f"Model loading failed for '{stage_name}': {e}") from e

    def evict_model(self, stage_name: str) -> bool:
        """
        Force immediate eviction of a specific model.

        Args:
            stage_name: Name of the model to evict

        Returns:
            True if model was evicted, False if not found
        """
        with self._lock:
            if stage_name in self._models:
                del self._models[stage_name]
                logger.info(f"Model '{stage_name}' forcibly evicted.")
                DeviceMemoryCleanup.run()
                return True
            return False

    def evict_all(self) -> None:
        """Force eviction of all cached models."""
        with self._lock:
            count = len(self._models)
            self._models.clear()
            logger.info(f"All {count} models forcibly evicted.")
        DeviceMemoryCleanup.run()

    def _start_eviction_timer(self) -> None:
        """Start a periodic background thread that evicts idle models."""

        def _evict_idle():
            with self._lock:
                now = time.time()
                to_evict = []

                for stage_name, (_, last_access) in self._models.items():
                    idle_time = now - last_access
                    if idle_time > self.idle_timeout_sec:
                        to_evict.append((stage_name, idle_time))

                for stage_name, idle_time in to_evict:
                    del self._models[stage_name]
                    logger.info(f"Model '{stage_name}' evicted after {idle_time:.0f}s idle time.")

                if to_evict:
                    DeviceMemoryCleanup.run()

            # Re-schedule the timer (Daemon mode allows clean exit)
            timer = threading.Timer(self._eviction_interval, _evict_idle)
            timer.daemon = True
            timer.start()

        # Start first check (Daemon mode allows clean exit)
        timer = threading.Timer(self._eviction_interval, _evict_idle)
        timer.daemon = True
        timer.start()
        logger.debug(f"Eviction timer started (interval={self._eviction_interval}s).")

    @property
    def cached_models(self) -> list[str]:
        """Return list of currently cached model names."""
        with self._lock:
            return list(self._models.keys())

    @property
    def model_count(self) -> int:
        """Return number of currently cached models."""
        with self._lock:
            return len(self._models)


class DeviceMemoryCleanup:
    """Static utility class for device-specific memory cleanup."""

    @staticmethod
    def run() -> None:
        """Perform aggressive memory cleanup across all detected devices."""
        # Python garbage collection
        gc.collect()

        # CUDA cleanup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.debug("CUDA memory cache cleared.")

        # MPS cleanup (Apple Silicon)
        if platform.system() == "Darwin":
            try:
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                    logger.debug("MPS memory cache cleared.")
            except (AttributeError, RuntimeError):
                # MPS may not be initialized or available
                pass

        logger.debug("Device memory cleanup complete.")


# Global singleton
lifecycle_manager = ModelLifecycleManager()
