from applications.web_app.src.routes import system as system_module


def test_healthcheck_returns_ok_when_all_services_healthy(client, monkeypatch):
    monkeypatch.setattr(system_module, "_check_database", lambda: (True, None))
    monkeypatch.setattr(system_module, "_check_redis", lambda: (True, None))
    monkeypatch.setattr(system_module, "_check_rabbitmq", lambda: (True, None))

    response = client.get("/healthcheck")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["services"]["database"]["ok"] is True


def test_healthcheck_returns_503_when_any_service_unhealthy(client, monkeypatch):
    monkeypatch.setattr(system_module, "_check_database", lambda: (False, "db down"))
    monkeypatch.setattr(system_module, "_check_redis", lambda: (True, None))
    monkeypatch.setattr(system_module, "_check_rabbitmq", lambda: (True, None))

    response = client.get("/healthcheck")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "degraded"
    assert body["services"]["database"]["error"] == "db down"


def test_metrics_returns_route_plan_counters(client, monkeypatch):
    monkeypatch.setattr(
        system_module.metrics_store,
        "get_all",
        lambda: {
            "route_plans.requests_total": 5,
            "route_plans.created_total": 4,
            "route_plans.validation_failed_total": 1,
            "route_plans.query_total": 7,
            "route_plans.analysis_cache_hit_total": 3,
            "route_plans.analysis_cache_miss_total": 2,
            "route_plans.mode.drive_total": 2,
            "route_plans.mode.transit_total": 1,
            "route_plans.mode.mixed_total": 1,
        },
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.get_json()
    assert body["route_plans"]["requests_total"] == 5
    assert body["route_plans"]["created_total"] == 4
    assert body["route_plans"]["by_mode"]["mixed"] == 1
