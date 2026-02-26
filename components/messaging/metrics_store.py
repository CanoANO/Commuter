import logging
import os
import threading
from collections import defaultdict

import redis

logger = logging.getLogger(__name__)


class MetricsStore:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0")
        self.hash_key = os.getenv("METRICS_HASH_KEY", "commuter:metrics")
        self._local = defaultdict(int)
        self._lock = threading.Lock()

    def _client(self):
        return redis.Redis.from_url(self.redis_url, decode_responses=True)

    def increment(self, metric_name: str, amount: int = 1) -> None:
        if amount == 0:
            return

        try:
            self._client().hincrby(self.hash_key, metric_name, amount)
            return
        except Exception as exc:
            logger.warning("metrics redis increment failed metric=%s error=%s", metric_name, exc)

        with self._lock:
            self._local[metric_name] += amount

    def get_all(self) -> dict[str, int]:
        values: dict[str, int] = {}

        try:
            raw = self._client().hgetall(self.hash_key)
            for key, value in raw.items():
                try:
                    values[key] = int(value)
                except (TypeError, ValueError):
                    values[key] = 0
        except Exception as exc:
            logger.warning("metrics redis fetch failed error=%s", exc)

        with self._lock:
            for key, value in self._local.items():
                values[key] = values.get(key, 0) + value

        return values
