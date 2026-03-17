import json
import logging
from datetime import timedelta

from components.services import GoogleMapsService
from components.database.gateways import RoutePlanGateway
from components.database.models import TaskStatus

logger = logging.getLogger(__name__)

class GoogleMapsCollector:
    def __init__(self, api_key: str | None = None):
        self.maps = GoogleMapsService(api_key=api_key)
        self.gateway = RoutePlanGateway()

    @staticmethod
    def _map_travel_mode(mode: str | None) -> str:
        mapping = {
            "drive": "DRIVE",
            "transit": "TRANSIT",
        }
        return mapping.get((mode or "drive").lower(), "DRIVE")

    @staticmethod
    def _parse_duration_seconds(duration_str: str | None) -> int:
        if not duration_str or not isinstance(duration_str, str) or not duration_str.endswith("s"):
            return 0
        try:
            return int(float(duration_str[:-1]))
        except ValueError:
            return 0

    @classmethod
    def _route_duration_seconds(cls, route_payload: dict | None) -> int:
        route = (route_payload or {}).get("routes", [{}])[0]
        return cls._parse_duration_seconds(route.get("duration"))

    def _resolve_location(self, address_text: str | None) -> dict:
        if not address_text or not address_text.strip():
            return {}

        normalized = address_text.strip()
        cached = self.gateway.get_cached_coordinates(normalized)
        if isinstance(cached, dict) and "lat" in cached and "lng" in cached:
            logger.info("Using cached coordinates address='%s'", normalized)
            return cached

        return self.maps.geocode_address(normalized)

    def process_task(self, task_id: str) -> None:
        task = self.gateway.get_task_inputs(task_id)
        if not task:
            logger.warning("Task not found task_id=%s", task_id)
            return

        logger.info(
            "Processing task task_id=%s locations=%s segment_modes=%s",
            task_id,
            task.get("location_texts"),
            task.get("segment_modes"),
        )

        self.gateway.update_task_status(task_id, TaskStatus.PROCESSING)

        try:
            location_texts = [
                str(item).strip()
                for item in (task.get("location_texts") or [])
                if str(item).strip()
            ]
            segment_modes = [
                str(item).strip().lower()
                for item in (task.get("segment_modes") or [])
            ]
            arrive_time = task.get("arrive_time")
            query_time = task.get("query_time")

            if len(location_texts) < 2:
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, "Task requires at least two locations")
                return

            if len(segment_modes) != len(location_texts) - 1:
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, "Segment modes length mismatch")
                return

            if any(mode not in {"drive", "transit"} for mode in segment_modes):
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, "Invalid segment mode")
                return

            resolved_points: list[dict] = []
            missing_indices: list[int] = []
            for index, location_text in enumerate(location_texts):
                point = self._resolve_location(location_text)
                if not point:
                    missing_indices.append(index)
                resolved_points.append(point)

            if missing_indices:
                missing_text = ", ".join(str(index + 1) for index in missing_indices)
                failure_message = f"Failed to geocode location index: {missing_text}"
                logger.warning(
                    "Task geocode failed task_id=%s missing_indices=%s",
                    task_id,
                    missing_text,
                )
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, failure_message)
                return

            segments: list[dict] = []
            segment_count = len(segment_modes)

            if arrive_time:
                current_arrival = arrive_time
                reverse_segments: list[dict] = []
                for index in range(segment_count - 1, -1, -1):
                    origin = resolved_points[index]
                    destination = resolved_points[index + 1]
                    mode = segment_modes[index]
                    travel_mode = self._map_travel_mode(mode)
                    route_payload = self.maps.compute_route(
                        origin,
                        destination,
                        mode=travel_mode,
                        arrival_time=current_arrival if travel_mode == "TRANSIT" else None,
                        departure_time=None,
                    )
                    duration_seconds = self._route_duration_seconds(route_payload)
                    if current_arrival and duration_seconds > 0:
                        current_arrival = current_arrival - timedelta(seconds=duration_seconds)
                    reverse_segments.append(
                        {
                            "from": location_texts[index],
                            "to": location_texts[index + 1],
                            "travel_mode": travel_mode,
                            "route": route_payload,
                        }
                    )
                segments = list(reversed(reverse_segments))
            else:
                current_departure = query_time
                for index in range(segment_count):
                    origin = resolved_points[index]
                    destination = resolved_points[index + 1]
                    mode = segment_modes[index]
                    travel_mode = self._map_travel_mode(mode)
                    route_payload = self.maps.compute_route(
                        origin,
                        destination,
                        mode=travel_mode,
                        arrival_time=None,
                        departure_time=current_departure if travel_mode == "TRANSIT" else None,
                    )
                    duration_seconds = self._route_duration_seconds(route_payload)
                    if current_departure and duration_seconds > 0:
                        current_departure = current_departure + timedelta(seconds=duration_seconds)
                    segments.append(
                        {
                            "from": location_texts[index],
                            "to": location_texts[index + 1],
                            "travel_mode": travel_mode,
                            "route": route_payload,
                        }
                    )

            unique_modes = sorted(set(segment_modes))
            aggregated_mode = unique_modes[0] if len(unique_modes) == 1 else "mixed"
            route_result = {
                "mode": aggregated_mode,
                "requested_segment_modes": segment_modes,
                "segments": segments,
            }

            self.gateway.save_route_result(
                task_id=task_id,
                result_json=json.dumps(route_result),
                location_points=resolved_points,
            )
            logger.info("Task processed successfully task_id=%s", task_id)
        except Exception as exc:
            logger.exception("Task processing exception task_id=%s", task_id)
            self.gateway.update_task_status(task_id, TaskStatus.FAILED, str(exc))
