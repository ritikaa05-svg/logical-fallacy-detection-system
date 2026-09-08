import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import redis
from redis import Redis

from backend.app.config import settings

logger = logging.getLogger(__name__)


class LogicHealthTracker:
    def __init__(self, storage_path: str = "data/logic_health.json", redis_client: Redis | None = None):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._history: list[dict[str, Any]] = self._load_initial()
        self._redis_available = redis_client is not None
        self._redis = redis_client
        self._reconnect_timer: int = 30

    def _try_reconnect(self) -> None:
        """Periodic Redis reconnection attempt."""
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._redis = client
            self._redis_available = True
            logger.info("HealthTracker: Redis reconnected.")
        except Exception:
            self._redis_available = False
            self._redis = None

    def _load_initial(self) -> list[dict[str, Any]]:
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load initial health history: {e}")
        return []

    def _load(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def _save(self, data: list[dict[str, Any]]):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save health history: {e}")

    def add_score(self, score: float):
        entry = {"timestamp": datetime.now().isoformat(), "score": float(score)}
        if self._redis_available:
            assert self._redis is not None
            try:
                self._redis.lpush("health:history", json.dumps(entry))
                self._redis.ltrim("health:history", 0, 49)
                return
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to local storage: {e}")
                self._redis_available = False
                self._try_reconnect()
        with self._lock:
            self._history.append(entry)
            self._history = self._history[-50:]
        self._save(self._history)

    def get_history(self) -> list[dict[str, Any]]:
        if self._redis_available:
            assert self._redis is not None
            try:
                raw = self._redis.lrange("health:history", 0, -1)
                return [json.loads(item) for item in raw]
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to local storage: {e}")
                self._redis_available = False
                self._try_reconnect()
        return self._load()

    def get_moving_average(self, window: int = 10) -> float:
        history = self.get_history()
        if not history:
            return 1.0
        scores = [h["score"] for h in history[-window:]]
        return sum(scores) / len(scores)


_redis_client = None
try:
    _redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    _redis_client.ping()
    logger.info(f"Health tracker Redis connected: {settings.REDIS_URL}")
except Exception as e:
    logger.warning(f"Health tracker Redis connection failed: {e}. Using local storage.")

health_tracker = LogicHealthTracker(redis_client=_redis_client)
