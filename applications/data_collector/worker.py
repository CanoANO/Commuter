import logging

from applications.data_collector import GoogleMapsCollector
from components.database.gateways import RoutePlanGateway
from components.messaging import QueueNames, RabbitMQConsumer, RabbitMQPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run() -> None:
    collector = GoogleMapsCollector()
    gateway = RoutePlanGateway()
    consumer = RabbitMQConsumer()
    publisher = RabbitMQPublisher()

    def _handle(message: dict) -> None:
        task_id = message.get("task_id")
        if not task_id:
            logger.warning("missing task_id in queue message=%s", message)
            return

        collector.process_task(task_id)
        task = gateway.get_route_plan(task_id)
        if task and task.get("status") == "SUCCESS" and task.get("result"):
            publisher.publish_json(
                queue_name=QueueNames.ROUTE_ANALYSIS,
                payload={"task_id": task_id},
            )

    consumer.consume_json(queue_name=QueueNames.ROUTE_TASKS, handler=_handle)


if __name__ == "__main__":
    run()
