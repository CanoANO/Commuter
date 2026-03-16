import logging
import os
import threading

logger = logging.getLogger(__name__)


def post_fork(server, worker):
    if os.getenv("JOB_BACKEND", "local").strip().lower() != "rabbitmq":
        return
    if os.getenv("EMBEDDED_CONSUMERS", "false").strip().lower() != "true":
        return
    count = int(os.getenv("EMBEDDED_CONSUMER_COUNT", "1"))
    from applications.data_collector.worker import run as run_collector
    from applications.data_analyzer.worker import run as run_analyzer
    for i in range(count):
        threading.Thread(target=run_collector, daemon=True, name=f"collector-{i}").start()
        threading.Thread(target=run_analyzer, daemon=True, name=f"analyzer-{i}").start()
    logger.info("Embedded consumers started count=%s worker_pid=%s", count, worker.pid)
