import logging
import os
import threading
from collections import defaultdict
from urllib.parse import urlparse

import redis

logger = logging.getLogger(__name__)


class MetricsStore:
    def __init__(self):
        self.redis_url = self._resolve_redis_url()
        self.hash_key = os.getenv("METRICS_HASH_KEY", "commuter:metrics")
        self._local = defaultdict(int)
        self._lock = threading.Lock()
        self._last_redis_error: str | None = None
        self._redis_client = self._build_client()

    @staticmethod
    def _resolve_redis_url() -> str:
        return (
            os.getenv("REDIS_URL")
            or os.getenv("KEY_VALUE_STORE_URL")
            or os.getenv("REDIS_TLS_URL")
            or f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
        )

    def _build_client(self):
        parsed = urlparse(self.redis_url)
        kwargs = {"decode_responses": True}

        if parsed.scheme == "rediss":
            ssl_mode = os.getenv("REDIS_SSL_CERT_REQS", "none").lower()
            kwargs["ssl_cert_reqs"] = None if ssl_mode == "none" else ssl_mode

        return redis.Redis.from_url(self.redis_url, **kwargs)

    def _client(self):
        return self._redis_client

    def _set_redis_error(self, exc: Exception) -> None:
        self._last_redis_error = f"{type(exc).__name__}: {exc}"

    def increment(self, metric_name: str, amount: int = 1) -> None:
        if amount == 0:
            return

        try:
            self._client().hincrby(self.hash_key, metric_name, amount)
            self._last_redis_error = None
            return
        except Exception as exc:
            self._set_redis_error(exc)
            logger.warning("metrics redis increment failed metric=%s error=%s", metric_name, exc)

        with self._lock:
            self._local[metric_name] += amount

    def get_all(self) -> dict[str, int]:
        values: dict[str, int] = {}

        try:
            raw = self._client().hgetall(self.hash_key)
            self._last_redis_error = None
            for key, value in raw.items():
                try:
                    values[key] = int(value)
                except (TypeError, ValueError):
                    values[key] = 0
        except Exception as exc:
            self._set_redis_error(exc)
            logger.warning("metrics redis fetch failed error=%s", exc)

        with self._lock:
            for key, value in self._local.items():
                values[key] = values.get(key, 0) + value

        return values

    def get_backend_status(self) -> dict[str, object]:
        parsed = urlparse(self.redis_url)
        connected = False

        try:
            self._client().ping()
            connected = True
            self._last_redis_error = None
        except Exception as exc:
            self._set_redis_error(exc)

        with self._lock:
            local_buffered_metric_count = len(self._local)

        return {
            "backend": "redis" if connected else "local_fallback",
            "connected": connected,
            "hash_key": self.hash_key,
            "redis_scheme": parsed.scheme,
            "redis_host": parsed.hostname,
            "local_buffered_metric_count": local_buffered_metric_count,
            "last_error": self._last_redis_error,
        }
