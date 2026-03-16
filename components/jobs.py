import logging
import os
from concurrent.futures import ThreadPoolExecutor

from applications.data_analyzer import build_task_analysis
from applications.data_collector import GoogleMapsCollector
from components.database.gateways import RoutePlanGateway
from components.messaging import AnalysisCache, QueueNames, RabbitMQPublisher

logger = logging.getLogger(__name__)


class _LocalJobRunner:
    def __init__(self):
        max_workers = int(os.getenv("LOCAL_JOB_WORKERS", "2"))
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.collector = GoogleMapsCollector()
        self.gateway = RoutePlanGateway()
        self.cache = AnalysisCache()

    def trigger(self, task_id: str) -> None:
        self.executor.submit(self._run_pipeline, task_id)

    def _run_pipeline(self, task_id: str) -> None:
        try:
            self.collector.process_task(task_id)
            task = self.gateway.get_route_plan(task_id)
            if task and task.get("status") == "SUCCESS" and task.get("result"):
                analysis = build_task_analysis(task)
                self.cache.set_analysis(task_id, analysis)
        except Exception:
            logger.exception("Local job pipeline failed task_id=%s", task_id)

class BackgroundJobManager:
    def __init__(self):
        self.backend = os.getenv("JOB_BACKEND", "rabbitmq").strip().lower()
        self.local_runner: _LocalJobRunner | None = None
        self.publisher: RabbitMQPublisher | None = None
        if self.backend == "local":
            self.local_runner = _LocalJobRunner()
        else:
            self.publisher = RabbitMQPublisher()

    def trigger_route_processing(self, task_id: str):
        if self.backend == "local":
            if self.local_runner is None:
                raise RuntimeError("Local job runner is not initialized")
            self.local_runner.trigger(task_id)
            return

        if self.publisher is None:
            raise RuntimeError("RabbitMQ publisher is not initialized")

        self.publisher.publish_json(
            queue_name=QueueNames.ROUTE_TASKS,
            payload={"task_id": task_id},
        )
