def test_create_route_plan_requires_at_least_two_locations(client, mocked_plan_dependencies):
    response = client.post("/route-plans", json={"locations": ["A"], "modes": []})

    assert response.status_code == 400
    assert response.get_json()["error"] == "locations must contain at least 2 addresses"
    mocked_plan_dependencies["metrics_increment"].assert_any_call("route_plans.requests_total")
    mocked_plan_dependencies["metrics_increment"].assert_any_call("route_plans.validation_failed_total")


def test_create_route_plan_rejects_invalid_mode(client, mocked_plan_dependencies):
    response = client.post(
        "/route-plans",
        json={"locations": ["A", "B"], "modes": ["bike"]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid mode in modes, only drive/transit allowed"


def test_create_route_plan_rejects_mismatched_modes_count(client, mocked_plan_dependencies):
    response = client.post(
        "/route-plans",
        json={"locations": ["A", "B", "C"], "modes": ["drive"]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "modes length must equal locations length minus one"


def test_create_route_plan_accepts_valid_multidest_payload(client, mocked_plan_dependencies):
    mocked_plan_dependencies["create_route_plan_from_locations"].return_value = "task-xyz"

    response = client.post(
        "/route-plans",
        json={"locations": ["A", "B", "C"], "modes": ["drive", "transit"]},
    )

    assert response.status_code == 201
    assert response.get_json()["task_id"] == "task-xyz"
    mocked_plan_dependencies["create_route_plan_from_locations"].assert_called_once()


def test_get_route_plan_returns_404_when_task_missing(client, mocked_plan_dependencies):
    mocked_plan_dependencies["get_route_plan"].return_value = None

    response = client.get("/route-plans/not-exist", headers={"Accept": "application/json"})

    assert response.status_code == 404
    assert response.get_json()["error"] == "Task not found"
    mocked_plan_dependencies["metrics_increment"].assert_any_call("route_plans.query_total")


def test_get_route_plan_renders_template_for_html(monkeypatch, client, mocked_plan_dependencies, plan_module):
    mocked_plan_dependencies["get_route_plan"].return_value = {
        "task_id": "task-html",
        "status": "PENDING",
        "result": None,
        "query_time": None,
        "arrive_time": None,
        "error_message": None,
    }

    monkeypatch.setattr(plan_module, "render_template", lambda template, task_id: f"rendered:{template}:{task_id}")

    response = client.get("/route-plans/task-html")

    assert response.status_code == 200
    assert "rendered:plan.html:task-html" in response.get_data(as_text=True)
