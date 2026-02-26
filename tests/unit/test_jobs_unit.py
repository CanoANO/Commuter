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

    manager = BackgroundJobManager()
    manager.trigger_route_processing("task-99")

    assert fake_publisher.calls == [(QueueNames.ROUTE_TASKS, {"task_id": "task-99"})]
