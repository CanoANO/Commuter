import pytest

pytest.importorskip("pika")

from components.jobs import BackgroundJobManager
from components.messaging import QueueNames


class _FakePublisher:
    def __init__(self):
        self.calls = []

    def publish_json(self, queue_name: str, payload: dict):
        self.calls.append((queue_name, payload))


def test_trigger_route_processing_publishes_task_message(monkeypatch):
    fake_publisher = _FakePublisher()
    monkeypatch.setattr("components.jobs.RabbitMQPublisher", lambda: fake_publisher)
    monkeypatch.delenv("JOB_BACKEND", raising=False)

    manager = BackgroundJobManager()
    manager.trigger_route_processing("task-99")

    assert fake_publisher.calls == [(QueueNames.ROUTE_TASKS, {"task_id": "task-99"})]


def test_trigger_route_processing_uses_local_runner_when_configured(monkeypatch):
    local_calls: list[str] = []

    class _FakeLocalRunner:
        def trigger(self, task_id: str) -> None:
            local_calls.append(task_id)

    monkeypatch.setenv("JOB_BACKEND", "local")
    monkeypatch.setattr("components.jobs._LocalJobRunner", lambda: _FakeLocalRunner())

    manager = BackgroundJobManager()
    manager.trigger_route_processing("task-local-1")

    assert local_calls == ["task-local-1"]
