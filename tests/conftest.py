import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture
def plan_module():
    try:
        from applications.web_app.src.routes import plan as plan_module_ref
    except Exception as exc:
        pytest.skip(f"plan module import failed: {exc}")
    return plan_module_ref


@pytest.fixture
def app(plan_module):
    try:
        from applications.web_app.src.app import create_app
    except Exception as exc:
        pytest.skip(f"flask app import failed: {exc}")

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mocked_plan_dependencies(monkeypatch, plan_module):
    dependencies = {
        "create_route_plan_from_locations": MagicMock(),
        "get_route_plan": MagicMock(),
        "trigger_route_processing": MagicMock(),
        "cache_get_analysis": MagicMock(),
        "cache_set_analysis": MagicMock(),
        "build_task_analysis": MagicMock(),
        "metrics_increment": MagicMock(),
    }

    monkeypatch.setattr(
        plan_module.route_plan_gateway,
        "create_route_plan_from_locations",
        dependencies["create_route_plan_from_locations"],
    )
    monkeypatch.setattr(plan_module.route_plan_gateway, "get_route_plan", dependencies["get_route_plan"])
    monkeypatch.setattr(plan_module.job_manager, "trigger_route_processing", dependencies["trigger_route_processing"])
    monkeypatch.setattr(plan_module.analysis_cache, "get_analysis", dependencies["cache_get_analysis"])
    monkeypatch.setattr(plan_module.analysis_cache, "set_analysis", dependencies["cache_set_analysis"])
    monkeypatch.setattr(plan_module.metrics_store, "increment", dependencies["metrics_increment"])
    monkeypatch.setattr(plan_module, "build_task_analysis", dependencies["build_task_analysis"])

    return dependencies


@pytest.fixture(autouse=True)
def _reset_route_analysis_timezone_cache(monkeypatch):
    monkeypatch.setenv("APP_TIMEZONE", "America/Toronto")
