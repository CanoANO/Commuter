import os
from datetime import datetime, timezone

import pika
import redis
from flask import Blueprint, Response, jsonify
from sqlalchemy import text

from components.database.session import engine
from components.messaging import MetricsStore

system_routes = Blueprint("system", __name__)
metrics_store = MetricsStore()


PROMETHEUS_METRIC_DEFS = {
    "route_plans.requests_total": (
        "commuter_route_plans_requests_total",
        "Counter of route plan create requests",
        "counter",
    ),
    "route_plans.created_total": (
        "commuter_route_plans_created_total",
        "Counter of successfully created route plans",
        "counter",
    ),
    "route_plans.validation_failed_total": (
        "commuter_route_plans_validation_failed_total",
        "Counter of route plan validation failures",
        "counter",
    ),
    "route_plans.query_total": (
        "commuter_route_plans_query_total",
        "Counter of route plan status queries",
        "counter",
    ),
    "route_plans.analysis_cache_hit_total": (
        "commuter_route_plans_analysis_cache_hit_total",
        "Counter of analysis cache hits",
        "counter",
    ),
    "route_plans.analysis_cache_miss_total": (
        "commuter_route_plans_analysis_cache_miss_total",
        "Counter of analysis cache misses",
        "counter",
    ),
    "route_plans.mode.drive_total": (
        "commuter_route_plans_mode_drive_total",
        "Counter of route plans requested in drive mode",
        "counter",
    ),
    "route_plans.mode.transit_total": (
        "commuter_route_plans_mode_transit_total",
        "Counter of route plans requested in transit mode",
        "counter",
    ),
    "route_plans.mode.mixed_total": (
        "commuter_route_plans_mode_mixed_total",
        "Counter of route plans requested in mixed mode",
        "counter",
    ),
}


def _to_prometheus_metrics(metrics_data: dict[str, int]) -> str:
    lines: list[str] = []
    for raw_key, (metric_name, help_text, metric_type) in PROMETHEUS_METRIC_DEFS.items():
        value = metrics_data.get(raw_key, 0)
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} {metric_type}")
        lines.append(f"{metric_name} {value}")

    return "\n".join(lines) + "\n"


def _check_database() -> tuple[bool, str | None]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def _check_redis() -> tuple[bool, str | None]:
    redis_url = metrics_store.redis_url
    try:
        client = redis.Redis.from_url(redis_url)
        client.ping()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _get_route_plan_db_snapshot() -> dict[str, object]:
    try:
        with engine.connect() as conn:
            total = int(conn.execute(text("SELECT COUNT(*) FROM route_tasks")).scalar_one())
            pending = int(
                conn.execute(text("SELECT COUNT(*) FROM route_tasks WHERE status = 'PENDING'"))
                .scalar_one()
            )
            processing = int(
                conn.execute(text("SELECT COUNT(*) FROM route_tasks WHERE status = 'PROCESSING'"))
                .scalar_one()
            )
            success = int(
                conn.execute(text("SELECT COUNT(*) FROM route_tasks WHERE status = 'SUCCESS'"))
                .scalar_one()
            )
            failed = int(
                conn.execute(text("SELECT COUNT(*) FROM route_tasks WHERE status = 'FAILED'"))
                .scalar_one()
            )

            mode_rows = conn.execute(
                text("SELECT mode, COUNT(*)::int AS count FROM route_tasks GROUP BY mode")
            ).mappings()
            by_mode = {"drive": 0, "transit": 0, "mixed": 0}
            for row in mode_rows:
                mode = str(row["mode"]) if row["mode"] is not None else ""
                if mode in by_mode:
                    by_mode[mode] = int(row["count"])

        return {
            "available": True,
            "total": total,
            "by_status": {
                "pending": pending,
                "processing": processing,
                "success": success,
                "failed": failed,
            },
            "by_mode": by_mode,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
        }


def _check_rabbitmq() -> tuple[bool, str | None]:
    amqp_url = os.getenv("AMQP_URL") or os.getenv("CLOUDAMQP_URL") or os.getenv("RABBITMQ_URL")
    if not amqp_url:
        amqp_url = f"amqp://{os.getenv('RABBITMQ_USER', 'commuter')}:{os.getenv('RABBITMQ_PASSWORD', 'commuter_password')}@{os.getenv('RABBITMQ_HOST', 'rabbitmq')}:{os.getenv('RABBITMQ_PORT', '5672')}/%2F"
    try:
        conn = pika.BlockingConnection(pika.URLParameters(amqp_url))
        conn.close()
        return True, None
    except Exception as exc:
        return False, str(exc)


@system_routes.route("/healthcheck", methods=["GET"])
def healthcheck():
    db_ok, db_error = _check_database()
    redis_ok, redis_error = _check_redis()
    rabbit_ok, rabbit_error = _check_rabbitmq()

    healthy = db_ok and redis_ok and rabbit_ok
    status_code = 200 if healthy else 503

    return (
        jsonify(
            {
                "status": "ok" if healthy else "degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "services": {
                    "database": {"ok": db_ok, "error": db_error},
                    "redis": {"ok": redis_ok, "error": redis_error},
                    "rabbitmq": {"ok": rabbit_ok, "error": rabbit_error},
                },
            }
        ),
        status_code,
    )


@system_routes.route("/metrics", methods=["GET"])
def metrics():
    all_metrics = metrics_store.get_all()
    backend_status = metrics_store.get_backend_status()
    db_snapshot = _get_route_plan_db_snapshot()

    created_total = all_metrics.get("route_plans.created_total", 0)
    requests_total = all_metrics.get("route_plans.requests_total", 0)
    db_total = db_snapshot.get("total", 0) if db_snapshot.get("available") else 0

    payload = {
        "route_plans": {
            "requests_total": requests_total,
            "created_total": created_total,
            "validation_failed_total": all_metrics.get("route_plans.validation_failed_total", 0),
            "query_total": all_metrics.get("route_plans.query_total", 0),
            "analysis_cache_hit_total": all_metrics.get("route_plans.analysis_cache_hit_total", 0),
            "analysis_cache_miss_total": all_metrics.get("route_plans.analysis_cache_miss_total", 0),
            "by_mode": {
                "drive": all_metrics.get("route_plans.mode.drive_total", 0),
                "transit": all_metrics.get("route_plans.mode.transit_total", 0),
                "mixed": all_metrics.get("route_plans.mode.mixed_total", 0),
            },
        },
        "diagnostics": {
            "metrics_backend": backend_status,
            "db_snapshot": db_snapshot,
            "suspected_metrics_pipeline_issue": bool(
                db_snapshot.get("available")
                and db_total > 0
                and created_total == 0
            ),
        },
        "raw": all_metrics,
    }

    return jsonify(payload)


@system_routes.route("/metrics/prometheus", methods=["GET"])
def metrics_prometheus():
    all_metrics = metrics_store.get_all()
    body = _to_prometheus_metrics(all_metrics)
    return Response(body, mimetype="text/plain; version=0.0.4")
