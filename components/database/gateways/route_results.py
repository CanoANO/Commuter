import json
from datetime import datetime, timezone

from components.database.session import SessionLocal
from components.database.models.routes import RouteTask, RouteResult, TaskStatus
from components.database.models.addresses import Address

class RouteResultGateway:
    @staticmethod
    def _normalize_segment_modes(
        mode: str | None,
        drive_part: str | None,
        has_transfer: bool,
    ) -> list[str]:
        normalized_mode = (mode or "drive").strip().lower()
        normalized_drive_part = (drive_part or "").strip().lower()

        if not has_transfer:
            return [normalized_mode if normalized_mode in {"drive", "transit"} else "drive"]

        if normalized_mode == "mixed":
            if normalized_drive_part == "second":
                return ["transit", "drive"]
            return ["drive", "transit"]

        default_mode = normalized_mode if normalized_mode in {"drive", "transit"} else "drive"
        return [default_mode, default_mode]

    def create_task_with_result(
        self,
        start_text: str,
        start_lat: float,
        start_lng: float,
        destination_text: str,
        destination_lat: float,
        destination_lng: float,
        transfer_text: str | None,
        transfer_lat: float | None,
        transfer_lng: float | None,
        drive_part: str | None,
        mode: str | None,
        arrive_time: datetime | None,
        result: dict,
    ) -> str:
        session = SessionLocal()
        try:
            start_address = Address(raw_text=start_text, lat=start_lat, lng=start_lng)
            session.add(start_address)
            session.flush()

            locations: list[int] = [start_address.id]

            transfer_address = None
            if transfer_text:
                transfer_address = Address(raw_text=transfer_text, lat=transfer_lat or 0.0, lng=transfer_lng or 0.0)
                session.add(transfer_address)
                session.flush()
                locations.append(transfer_address.id)

            destination_address = Address(raw_text=destination_text, lat=destination_lat, lng=destination_lng)
            session.add(destination_address)
            session.flush()
            locations.append(destination_address.id)

            segment_modes = self._normalize_segment_modes(
                mode=mode,
                drive_part=drive_part,
                has_transfer=transfer_address is not None,
            )

            task = RouteTask(
                status=TaskStatus.SUCCESS,
                locations=locations,
                segment_modes=segment_modes,
                arrive_time=arrive_time,
                query_time=datetime.now(timezone.utc),
                error_message=None,
            )
            session.add(task)
            session.flush()

            result_row = RouteResult(
                task_id=task.id,
                result_json=json.dumps(result),
            )
            session.add(result_row)
            session.commit()

            return str(task.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
