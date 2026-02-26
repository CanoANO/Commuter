def test_create_route_plan_requires_start_and_destination(client, mocked_plan_dependencies):
    response = client.post("/route-plans", json={"start_address": "", "destination_address": ""})

    assert response.status_code == 400
    assert response.get_json()["error"] == "start_address and destination_address are required"
    mocked_plan_dependencies["metrics_increment"].assert_any_call("route_plans.requests_total")
    mocked_plan_dependencies["metrics_increment"].assert_any_call("route_plans.validation_failed_total")


def test_create_route_plan_rejects_invalid_mode(client, mocked_plan_dependencies):
    response = client.post(
        "/route-plans",
        json={"start_address": "A", "destination_address": "B", "mode": "bike"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid mode"


def test_create_route_plan_rejects_invalid_drive_part(client, mocked_plan_dependencies):
    response = client.post(
        "/route-plans",
        json={
            "start_address": "A",
            "destination_address": "B",
            "mode": "mixed",
            "transfer_address": "T",
            "drive_part": "third",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid drive_part"


def test_create_route_plan_requires_transfer_for_mixed(client, mocked_plan_dependencies):
    response = client.post(
        "/route-plans",
        json={
            "start_address": "A",
            "destination_address": "B",
            "mode": "mixed",
            "drive_part": "first",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "transfer_address is required for mixed mode"


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
