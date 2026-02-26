import logging

from applications.data_analyzer import build_task_analysis
from components.database.gateways import RoutePlanGateway
from components.messaging import AnalysisCache, QueueNames, RabbitMQConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run() -> None:
    gateway = RoutePlanGateway()
    cache = AnalysisCache()
    consumer = RabbitMQConsumer()

    def _handle(message: dict) -> None:
        task_id = message.get("task_id")
        if not task_id:
            logger.warning("missing task_id in queue message=%s", message)
            return

        task = gateway.get_route_plan(task_id)
        if not task or task.get("status") != "SUCCESS" or not task.get("result"):
            logger.info("skip analysis task_id=%s status=%s", task_id, task.get("status") if task else None)
            return

        analysis = build_task_analysis(task)
        cache.set_analysis(task_id, analysis)
        logger.info("analysis cached task_id=%s", task_id)

    consumer.consume_json(queue_name=QueueNames.ROUTE_ANALYSIS, handler=_handle)


if __name__ == "__main__":
    run()
