from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest


@pytest.fixture
def collector_module():
    try:
        from applications.data_collector import google_maps_collector as module_ref
    except Exception as exc:
        pytest.skip(f"collector module import failed: {exc}")
    return module_ref


def test_map_travel_mode_defaults_to_drive(collector_module):
    assert collector_module.GoogleMapsCollector._map_travel_mode(None) == "DRIVE"
    assert collector_module.GoogleMapsCollector._map_travel_mode("drive") == "DRIVE"
    assert collector_module.GoogleMapsCollector._map_travel_mode("transit") == "TRANSIT"
    assert collector_module.GoogleMapsCollector._map_travel_mode("unknown") == "DRIVE"


def test_process_task_marks_failed_when_geocode_missing(monkeypatch, collector_module):
    collector = collector_module.GoogleMapsCollector(api_key="x")

    collector.gateway = MagicMock()
    collector.maps = MagicMock()

    collector.gateway.get_task_inputs.return_value = {
        "task_id": "task-1",
        "start_text": "A",
        "destination_text": "B",
        "transfer_text": None,
        "mode": "drive",
        "drive_part": None,
        "arrive_time": None,
    }

    collector.maps.geocode_address.side_effect = [{}, {"lat": 1.0, "lng": 2.0}]

    collector.process_task("task-1")

    collector.gateway.update_task_status.assert_any_call("task-1", collector_module.TaskStatus.PROCESSING)
    collector.gateway.update_task_status.assert_any_call(
        "task-1", collector_module.TaskStatus.FAILED, "Failed to geocode start address"
    )
    collector.gateway.save_route_result.assert_not_called()


def test_process_task_saves_result_for_drive_mode(collector_module):
    collector = collector_module.GoogleMapsCollector(api_key="x")

    collector.gateway = MagicMock()
    collector.maps = MagicMock()

    collector.gateway.get_task_inputs.return_value = {
        "task_id": "task-2",
        "start_text": "A",
        "destination_text": "B",
        "transfer_text": None,
        "mode": "drive",
        "drive_part": None,
        "arrive_time": None,
    }

    collector.maps.geocode_address.side_effect = [
        {"lat": 1.0, "lng": 2.0},
        {"lat": 3.0, "lng": 4.0},
    ]
    collector.maps.compute_route.return_value = {"routes": [{"duration": "120s"}]}

    collector.process_task("task-2")

    collector.gateway.update_task_status.assert_any_call("task-2", collector_module.TaskStatus.PROCESSING)
    collector.gateway.save_route_result.assert_called_once()


def test_process_task_transit_uses_query_time_as_departure_time(collector_module):
    collector = collector_module.GoogleMapsCollector(api_key="x")

    collector.gateway = MagicMock()
    collector.maps = MagicMock()

    query_time = datetime(2026, 2, 25, 20, 0, 0, tzinfo=timezone.utc)

    collector.gateway.get_task_inputs.return_value = {
        "task_id": "task-3",
        "start_text": "A",
        "destination_text": "B",
        "transfer_text": None,
        "mode": "transit",
        "drive_part": None,
        "arrive_time": None,
        "query_time": query_time,
    }

    collector.maps.geocode_address.side_effect = [
        {"lat": 1.0, "lng": 2.0},
        {"lat": 3.0, "lng": 4.0},
    ]
    collector.maps.compute_route.return_value = {"routes": [{"duration": "120s"}]}

    collector.process_task("task-3")

    _, kwargs = collector.maps.compute_route.call_args
    assert kwargs["mode"] == "TRANSIT"
    assert kwargs["arrival_time"] is None
    assert kwargs["departure_time"] == query_time


def test_process_task_uses_cached_coordinates_before_geocode(collector_module):
    collector = collector_module.GoogleMapsCollector(api_key="x")

    collector.gateway = MagicMock()
    collector.maps = MagicMock()

    collector.gateway.get_task_inputs.return_value = {
        "task_id": "task-cache",
        "start_text": "A",
        "destination_text": "B",
        "transfer_text": None,
        "mode": "drive",
        "drive_part": None,
        "arrive_time": None,
    }
    collector.gateway.get_cached_coordinates.side_effect = [
        {"lat": 10.0, "lng": 20.0},
        {"lat": 30.0, "lng": 40.0},
    ]
    collector.maps.compute_route.return_value = {"routes": [{"duration": "120s"}]}

    collector.process_task("task-cache")

    collector.maps.geocode_address.assert_not_called()
    collector.gateway.save_route_result.assert_called_once()


def test_process_task_falls_back_to_geocode_when_cache_miss(collector_module):
    collector = collector_module.GoogleMapsCollector(api_key="x")

    collector.gateway = MagicMock()
    collector.maps = MagicMock()

    collector.gateway.get_task_inputs.return_value = {
        "task_id": "task-cache-miss",
        "start_text": "A",
        "destination_text": "B",
        "transfer_text": None,
        "mode": "drive",
        "drive_part": None,
        "arrive_time": None,
    }
    collector.gateway.get_cached_coordinates.return_value = None
    collector.maps.geocode_address.side_effect = [
        {"lat": 1.0, "lng": 2.0},
        {"lat": 3.0, "lng": 4.0},
    ]
    collector.maps.compute_route.return_value = {"routes": [{"duration": "120s"}]}

    collector.process_task("task-cache-miss")

    assert collector.maps.geocode_address.call_count == 2
    collector.gateway.save_route_result.assert_called_once()
