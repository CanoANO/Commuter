import json
import logging
import os

import redis

logger = logging.getLogger(__name__)


class AnalysisCache:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0")
        self.ttl_seconds = int(os.getenv("ANALYSIS_CACHE_TTL_SECONDS", "86400"))
        self.key_prefix = os.getenv("ANALYSIS_CACHE_PREFIX", "route_analysis:")

    def _key(self, task_id: str) -> str:
        return f"{self.key_prefix}{task_id}"

    def _client(self):
        return redis.Redis.from_url(self.redis_url, decode_responses=True)

    def get_analysis(self, task_id: str) -> dict | None:
        try:
            raw = self._client().get(self._key(task_id))
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("analysis cache get failed task_id=%s error=%s", task_id, exc)
            return None

    def set_analysis(self, task_id: str, analysis: dict) -> None:
        try:
            self._client().setex(self._key(task_id), self.ttl_seconds, json.dumps(analysis))
        except Exception as exc:
            logger.warning("analysis cache set failed task_id=%s error=%s", task_id, exc)
