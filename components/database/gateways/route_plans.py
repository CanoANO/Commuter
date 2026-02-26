import json
import uuid
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from components.database.session import SessionLocal
from components.database.models import RouteTask, RouteResult, TaskStatus, TaskMode, DrivePart, Address

class RoutePlanGateway:
    @staticmethod
    def _parse_arrive_time(arrive_time_raw: str | None) -> datetime | None:
        if not arrive_time_raw:
            return None

        normalized = arrive_time_raw.strip()
        if not normalized:
            return None

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            timezone_name = os.getenv("APP_TIMEZONE", "America/Toronto")
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))

        return parsed.astimezone(timezone.utc)

    def create_route_plan(
        self,
        start_text: str,
        transfer_text: str | None,
        destination_text: str,
        drive_part: str | None,
        mode: str | None,
        arrive_time_raw: str | None,
    ) -> str:
        arrive_time = self._parse_arrive_time(arrive_time_raw)

        query_time = datetime.now(timezone.utc)

        session = SessionLocal()
        try:
            start_address = Address(raw_text=start_text, lat=0.0, lng=0.0)
            session.add(start_address)
            session.flush()

            transfer_address = None
            if transfer_text:
                transfer_address = Address(raw_text=transfer_text, lat=0.0, lng=0.0)
                session.add(transfer_address)
                session.flush()

            destination_address = Address(raw_text=destination_text, lat=0.0, lng=0.0)
            session.add(destination_address)
            session.flush()

            task = RouteTask(
                status=TaskStatus.PENDING,
                start_address_id=start_address.id,
                transfer_address_id=transfer_address.id if transfer_address else None,
                destination_address_id=destination_address.id,
                mode=TaskMode(mode) if mode else TaskMode.drive,
                drive_part=DrivePart(drive_part) if drive_part else None,
                arrive_time=arrive_time,
                query_time=query_time,
                error_message=None,
            )
            session.add(task)
            session.commit()

            return str(task.id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_route_plan(self, task_id: str) -> dict | None:
        session = SessionLocal()
        try:
            try:
                task_uuid = uuid.UUID(task_id)
            except ValueError:
                return None

            task = session.get(RouteTask, task_uuid)
            if not task:
                return None

            result_payload = None
            if task.result and task.result.result_json:
                try:
                    result_payload = json.loads(task.result.result_json)
                except json.JSONDecodeError:
                    result_payload = task.result.result_json

            return {
                "task_id": str(task.id),
                "status": task.status.value,
                "error_message": task.error_message,
                "query_time": task.query_time.isoformat() if task.query_time else None,
                "arrive_time": task.arrive_time.isoformat() if task.arrive_time else None,
                "result": result_payload,
            }
        finally:
            session.close()

    def get_task_inputs(self, task_id: str) -> dict | None:
        session = SessionLocal()
        try:
            try:
                task_uuid = uuid.UUID(task_id)
            except ValueError:
                return None

            task = session.get(RouteTask, task_uuid)
            if not task:
                return None

            return {
                "task_id": str(task.id),
                "start_text": task.start_address.raw_text if task.start_address else None,
                "transfer_text": task.transfer_address.raw_text if task.transfer_address else None,
                "destination_text": task.destination_address.raw_text if task.destination_address else None,
                "drive_part": task.drive_part.value if task.drive_part else None,
                "mode": task.mode.value if task.mode else None,
                "arrive_time": task.arrive_time,
                "query_time": task.query_time,
            }
        finally:
            session.close()

    def update_task_status(self, task_id: str, status: TaskStatus, error_message: str | None = None) -> None:
        session = SessionLocal()
        try:
            task = session.get(RouteTask, uuid.UUID(task_id))
            if not task:
                return
            task.status = status
            task.error_message = error_message
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_route_result(
        self,
        task_id: str,
        start_lat: float,
        start_lng: float,
        destination_lat: float,
        destination_lng: float,
        transfer_lat: float | None,
        transfer_lng: float | None,
        result_json: str,
    ) -> None:
        session = SessionLocal()
        try:
            task = session.get(RouteTask, uuid.UUID(task_id))
            if not task:
                return

            if task.start_address:
                task.start_address.lat = start_lat
                task.start_address.lng = start_lng
            if task.transfer_address and transfer_lat is not None and transfer_lng is not None:
                task.transfer_address.lat = transfer_lat
                task.transfer_address.lng = transfer_lng
            if task.destination_address:
                task.destination_address.lat = destination_lat
                task.destination_address.lng = destination_lng

            if task.result:
                task.result.result_json = result_json
            else:
                result_row = RouteResult(
                    task_id=task.id,
                    result_json=result_json,
                )
                session.add(result_row)

            task.status = TaskStatus.SUCCESS
            task.error_message = None
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
