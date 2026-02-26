import json

import pytest

pytest.importorskip("redis")

from components.messaging.analysis_cache import AnalysisCache


class _FakeRedisClient:
    def __init__(self):
        self.store = {}
        self.setex_calls = []

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.setex_calls.append((key, ttl, value))


def test_analysis_cache_set_and_get(monkeypatch):
    fake_client = _FakeRedisClient()
    monkeypatch.setattr("components.messaging.analysis_cache.redis.Redis.from_url", lambda *args, **kwargs: fake_client)

    cache = AnalysisCache()
    payload = {"version": 2, "summary": {"mode": "DRIVE"}}

    cache.set_analysis("task-1", payload)
    loaded = cache.get_analysis("task-1")

    assert loaded == payload
    assert fake_client.setex_calls


def test_analysis_cache_get_returns_none_on_invalid_json(monkeypatch):
    fake_client = _FakeRedisClient()
    fake_client.store["route_analysis:task-bad"] = "not-json"
    monkeypatch.setattr("components.messaging.analysis_cache.redis.Redis.from_url", lambda *args, **kwargs: fake_client)

    cache = AnalysisCache()

    assert cache.get_analysis("task-bad") is None


def test_analysis_cache_set_swallows_exceptions(monkeypatch):
    class _BrokenClient:
        def setex(self, *_args, **_kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr("components.messaging.analysis_cache.redis.Redis.from_url", lambda *args, **kwargs: _BrokenClient())

    cache = AnalysisCache()
    cache.set_analysis("task-1", {"a": 1})

    assert True
