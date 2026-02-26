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
            "mixed": "DRIVE",
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

    def process_task(self, task_id: str) -> None:
        task = self.gateway.get_task_inputs(task_id)
        if not task:
            logger.warning("Task not found task_id=%s", task_id)
            return

        logger.info(
            "Processing task task_id=%s mode=%s drive_part=%s start='%s' transfer='%s' destination='%s'",
            task_id,
            task.get("mode"),
            task.get("drive_part"),
            task.get("start_text"),
            task.get("transfer_text"),
            task.get("destination_text"),
        )

        self.gateway.update_task_status(task_id, TaskStatus.PROCESSING)

        try:
            start_text = task.get("start_text") or ""
            destination_text = task.get("destination_text") or ""
            start_loc = self.maps.geocode_address(start_text)
            dest_loc = self.maps.geocode_address(destination_text)
            transfer_text = task.get("transfer_text")
            transfer_loc = self.maps.geocode_address(transfer_text) if transfer_text else None
            mode = (task.get("mode") or "drive").lower()
            drive_part = (task.get("drive_part") or "").lower() or None
            arrive_time = task.get("arrive_time")
            query_time = task.get("query_time")

            if not start_loc or not dest_loc:
                missing_parts: list[str] = []
                if not start_loc:
                    missing_parts.append("start")
                if not dest_loc:
                    missing_parts.append("destination")
                failure_message = f"Failed to geocode {', '.join(missing_parts)} address"
                logger.warning(
                    "Task geocode failed task_id=%s missing=%s start='%s' destination='%s'",
                    task_id,
                    ",".join(missing_parts),
                    start_text,
                    destination_text,
                )
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, failure_message)
                return

            if mode == "mixed" and not transfer_loc:
                logger.warning("Task mixed mode transfer geocode failed task_id=%s transfer='%s'", task_id, transfer_text)
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, "Mixed mode requires a valid transfer address")
                return

            if mode == "mixed" and drive_part not in {"first", "second"}:
                logger.warning("Task mixed mode invalid drive_part task_id=%s drive_part=%s", task_id, drive_part)
                self.gateway.update_task_status(task_id, TaskStatus.FAILED, "Mixed mode requires drive_part to be first or second")
                return

            if mode == "mixed":
                if drive_part == "first":
                    first_leg_mode = "DRIVE"
                    second_leg_mode = "TRANSIT"
                else:
                    first_leg_mode = "TRANSIT"
                    second_leg_mode = "DRIVE"

                if drive_part == "first":
                    first_leg = self.maps.compute_route(
                        start_loc,
                        transfer_loc,
                        mode="DRIVE",
                    )
                    first_leg_seconds = self._route_duration_seconds(first_leg)
                    earliest_transit_departure = (
                        query_time + timedelta(seconds=first_leg_seconds)
                        if query_time and first_leg_seconds > 0
                        else query_time
                    )
                    second_leg = self.maps.compute_route(
                        transfer_loc,
                        dest_loc,
                        mode="TRANSIT",
                        arrival_time=arrive_time,
                        departure_time=None if arrive_time else earliest_transit_departure,
                    )
                else:
                    second_leg = self.maps.compute_route(
                        transfer_loc,
                        dest_loc,
                        mode="DRIVE",
                    )
                    second_leg_seconds = self._route_duration_seconds(second_leg)
                    target_transit_arrival = (
                        arrive_time - timedelta(seconds=second_leg_seconds)
                        if arrive_time and second_leg_seconds > 0
                        else arrive_time
                    )
                    first_leg = self.maps.compute_route(
                        start_loc,
                        transfer_loc,
                        mode="TRANSIT",
                        arrival_time=target_transit_arrival,
                        departure_time=None if target_transit_arrival else query_time,
                    )

                route_result = {
                    "mode": "mixed",
                    "drive_part": drive_part,
                    "segments": [
                        {
                            "from": "start",
                            "to": "transfer",
                            "travel_mode": first_leg_mode,
                            "route": first_leg,
                        },
                        {
                            "from": "transfer",
                            "to": "destination",
                            "travel_mode": second_leg_mode,
                            "route": second_leg,
                        },
                    ],
                }
            else:
                travel_mode = self._map_travel_mode(mode)
                transit_departure_time = query_time if travel_mode == "TRANSIT" and not arrive_time else None
                single_route = self.maps.compute_route(
                    start_loc,
                    dest_loc,
                    mode=travel_mode,
                    arrival_time=arrive_time if travel_mode == "TRANSIT" else None,
                    departure_time=transit_departure_time,
                )
                route_result = {
                    "mode": mode,
                    "travel_mode": travel_mode,
                    "segments": [
                        {
                            "from": "start",
                            "to": "destination",
                            "travel_mode": travel_mode,
                            "route": single_route,
                        }
                    ],
                }

            self.gateway.save_route_result(
                task_id=task_id,
                start_lat=start_loc["lat"],
                start_lng=start_loc["lng"],
                destination_lat=dest_loc["lat"],
                destination_lng=dest_loc["lng"],
                transfer_lat=transfer_loc["lat"] if transfer_loc else None,
                transfer_lng=transfer_loc["lng"] if transfer_loc else None,
                result_json=json.dumps(route_result),
            )
            logger.info("Task processed successfully task_id=%s", task_id)
        except Exception as exc:
            logger.exception("Task processing exception task_id=%s", task_id)
            self.gateway.update_task_status(task_id, TaskStatus.FAILED, str(exc))
