import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable

import pika

logger = logging.getLogger(__name__)


class QueueNames:
    ROUTE_TASKS = os.getenv("ROUTE_TASK_QUEUE", "route_tasks")
    ROUTE_ANALYSIS = os.getenv("ROUTE_ANALYSIS_QUEUE", "route_analysis")


@dataclass
class _ConnectionSettings:
    amqp_url: str
    connect_retries: int
    retry_interval_seconds: int


def _get_settings() -> _ConnectionSettings:
    amqp_url = os.getenv("AMQP_URL") or os.getenv("CLOUDAMQP_URL") or os.getenv("RABBITMQ_URL")
    if not amqp_url:
        amqp_url = f"amqp://{os.getenv('RABBITMQ_USER', 'commuter')}:{os.getenv('RABBITMQ_PASSWORD', 'commuter_password')}@{os.getenv('RABBITMQ_HOST', 'rabbitmq')}:{os.getenv('RABBITMQ_PORT', '5672')}/%2F"
    
    return _ConnectionSettings(
        amqp_url=amqp_url,
        connect_retries=int(os.getenv("AMQP_CONNECT_RETRIES", "30")),
        retry_interval_seconds=int(os.getenv("AMQP_RETRY_INTERVAL_SECONDS", "2")),
    )


def _create_connection(is_publisher: bool = False) -> pika.BlockingConnection:
    settings = _get_settings()
    params = pika.URLParameters(settings.amqp_url)

    retries = 2 if is_publisher else settings.connect_retries
    for attempt in range(1, retries + 1):
        try:
            return pika.BlockingConnection(params)
        except Exception as exc:
            if attempt >= retries:
                raise
            logger.warning(
                "RabbitMQ connect failed attempt=%s/%s error=%s",
                attempt,
                retries,
                exc,
            )
            time.sleep(settings.retry_interval_seconds)

    raise RuntimeError("Unable to connect to RabbitMQ")


class RabbitMQPublisher:
    def publish_json(self, queue_name: str, payload: dict) -> None:
        connection = _create_connection(is_publisher=True)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=json.dumps(payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            connection.close()


class RabbitMQConsumer:
    def consume_json(self, queue_name: str, handler: Callable[[dict], None]) -> None:
        while True:
            connection = None
            try:
                connection = _create_connection()
                channel = connection.channel()
                channel.queue_declare(queue=queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)

                def _callback(ch, method, _properties, body):
                    try:
                        message = json.loads(body.decode("utf-8"))
                        handler(message)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception as exc:
                        logger.exception("Queue handler error queue=%s error=%s", queue_name, exc)
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

                channel.basic_consume(queue=queue_name, on_message_callback=_callback)
                logger.info("RabbitMQ consumer started queue=%s", queue_name)
                channel.start_consuming()
            except Exception as exc:
                logger.exception("RabbitMQ consumer stopped queue=%s error=%s", queue_name, exc)
                time.sleep(2)
            finally:
                if connection and connection.is_open:
                    connection.close()
