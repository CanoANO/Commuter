def test_create_route_plan_triggers_background_job(client, mocked_plan_dependencies):
    mocked_plan_dependencies["create_route_plan"].return_value = "task-123"

    response = client.post(
        "/route-plans",
        json={
            "start_address": "A",
            "destination_address": "B",
            "mode": "drive",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["task_id"] == "task-123"
    mocked_plan_dependencies["create_route_plan"].assert_called_once()
    mocked_plan_dependencies["trigger_route_processing"].assert_called_once_with("task-123")


def test_get_route_plan_uses_cached_analysis_when_version_matches(client, mocked_plan_dependencies):
    mocked_plan_dependencies["get_route_plan"].return_value = {
        "task_id": "task-1",
        "status": "SUCCESS",
        "result": {"segments": []},
        "query_time": "2026-02-25T21:00:00+00:00",
        "arrive_time": None,
        "error_message": None,
    }
    mocked_plan_dependencies["cache_get_analysis"].return_value = {
        "version": 2,
        "summary": {"mode": "DRIVE"},
        "segments": [],
    }

    response = client.get("/route-plans/task-1", headers={"Accept": "application/json"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["analysis"]["version"] == 2
    mocked_plan_dependencies["build_task_analysis"].assert_not_called()
    mocked_plan_dependencies["cache_set_analysis"].assert_not_called()


def test_get_route_plan_recomputes_analysis_when_cache_is_old_version(client, mocked_plan_dependencies):
    task_payload = {
        "task_id": "task-2",
        "status": "SUCCESS",
        "result": {"segments": []},
        "query_time": "2026-02-25T21:00:00+00:00",
        "arrive_time": None,
        "error_message": None,
    }
    computed_analysis = {"version": 2, "summary": {"mode": "DRIVE"}, "segments": []}

    mocked_plan_dependencies["get_route_plan"].return_value = task_payload
    mocked_plan_dependencies["cache_get_analysis"].return_value = {"version": 1, "summary": {}, "segments": []}
    mocked_plan_dependencies["build_task_analysis"].return_value = computed_analysis

    response = client.get("/route-plans/task-2", headers={"Accept": "application/json"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["analysis"]["version"] == 2
    mocked_plan_dependencies["build_task_analysis"].assert_called_once_with(task_payload)
    mocked_plan_dependencies["cache_set_analysis"].assert_called_once_with("task-2", computed_analysis)
