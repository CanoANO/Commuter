import json
from datetime import datetime, timezone

from components.database.session import SessionLocal
from components.database.models.routes import RouteTask, RouteResult, TaskStatus, TaskMode, DrivePart
from components.database.models.addresses import Address

class RouteResultGateway:
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

            transfer_address = None
            if transfer_text:
                transfer_address = Address(raw_text=transfer_text, lat=transfer_lat or 0.0, lng=transfer_lng or 0.0)
                session.add(transfer_address)
                session.flush()

            destination_address = Address(raw_text=destination_text, lat=destination_lat, lng=destination_lng)
            session.add(destination_address)
            session.flush()

            task = RouteTask(
                status=TaskStatus.SUCCESS,
                start_address_id=start_address.id,
                transfer_address_id=transfer_address.id if transfer_address else None,
                destination_address_id=destination_address.id,
                mode=TaskMode(mode) if mode else TaskMode.drive,
                drive_part=DrivePart(drive_part) if drive_part else None,
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
