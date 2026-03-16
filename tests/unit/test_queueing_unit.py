from types import SimpleNamespace

import pytest

pytest.importorskip("pika")

from components.messaging import queueing


def test_get_settings_reads_env(monkeypatch):
    monkeypatch.setenv("AMQP_URL", "amqp://u:p@mq:5672/%2F")
    monkeypatch.setenv("AMQP_CONNECT_RETRIES", "5")
    monkeypatch.setenv("AMQP_RETRY_INTERVAL_SECONDS", "1")

    settings = queueing._get_settings()

    assert settings.amqp_url == "amqp://u:p@mq:5672/%2F"
    assert settings.connect_retries == 5
    assert settings.retry_interval_seconds == 1


def test_create_connection_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def _fake_blocking_connection(_params):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("connect failed")
        return "conn"

    monkeypatch.setattr(queueing.pika, "BlockingConnection", _fake_blocking_connection)
    monkeypatch.setattr(queueing.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        queueing,
        "_get_settings",
        lambda: SimpleNamespace(amqp_url="amqp://x", connect_retries=3, retry_interval_seconds=0),
    )

    connection = queueing._create_connection()

    assert connection == "conn"
    assert calls["count"] == 3


def test_publisher_declares_queue_and_publishes(monkeypatch):
    published = {}

    class _FakeChannel:
        def queue_declare(self, queue, durable):
            published["queue"] = (queue, durable)

        def basic_publish(self, exchange, routing_key, body, properties):
            published["exchange"] = exchange
            published["routing_key"] = routing_key
            published["body"] = body
            published["delivery_mode"] = properties.delivery_mode

    class _FakeConnection:
        def __init__(self):
            self.closed = False

        def channel(self):
            return _FakeChannel()

        def close(self):
            self.closed = True

    fake_conn = _FakeConnection()
    monkeypatch.setattr(queueing, "_create_connection", lambda is_publisher=False: fake_conn)

    publisher = queueing.RabbitMQPublisher()
    publisher.publish_json("route_tasks", {"task_id": "abc"})

    assert published["queue"] == ("route_tasks", True)
    assert published["routing_key"] == "route_tasks"
    assert '"task_id": "abc"' in published["body"]
    assert published["delivery_mode"] == 2
    assert fake_conn.closed is True
