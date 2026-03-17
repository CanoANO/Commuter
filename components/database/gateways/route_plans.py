import json
import uuid
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_

from components.database.session import SessionLocal
from components.database.models import RouteTask, RouteResult, TaskStatus, Address

class RoutePlanGateway:
    @staticmethod
    def _sanitize_segment_modes(segment_modes: list[str]) -> list[str]:
        sanitized: list[str] = []
        for item in segment_modes:
            mode = (item or "").strip().lower()
            if mode in {"drive", "transit"}:
                sanitized.append(mode)
        return sanitized

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

    @staticmethod
    def _derive_legacy_mode_fields(segment_modes: list[str]) -> tuple[str | None, str | None]:
        cleaned = [(item or "").strip().lower() for item in (segment_modes or []) if (item or "").strip()]
        if not cleaned:
            return None, None

        if len(cleaned) == 1:
            return cleaned[0], None

        if len(cleaned) == 2 and set(cleaned) == {"drive", "transit"}:
            return "mixed", "first" if cleaned[0] == "drive" else "second"

        if all(item == cleaned[0] for item in cleaned):
            return cleaned[0], None

        return None, None

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
        location_texts = [start_text]
        if transfer_text:
            location_texts.append(transfer_text)
        location_texts.append(destination_text)

        segment_modes = self._normalize_segment_modes(
            mode=mode,
            drive_part=drive_part,
            has_transfer=transfer_text is not None,
        )
        return self.create_route_plan_from_locations(
            location_texts=location_texts,
            segment_modes=segment_modes,
            arrive_time_raw=arrive_time_raw,
        )

    def create_route_plan_from_locations(
        self,
        location_texts: list[str],
        segment_modes: list[str],
        arrive_time_raw: str | None,
    ) -> str:
        arrive_time = self._parse_arrive_time(arrive_time_raw)
        query_time = datetime.now(timezone.utc)
        cleaned_locations = [(item or "").strip() for item in location_texts if (item or "").strip()]
        cleaned_modes = self._sanitize_segment_modes(segment_modes)

        if len(cleaned_locations) < 2:
            raise ValueError("At least two locations are required")
        if len(cleaned_modes) != len(cleaned_locations) - 1:
            raise ValueError("segment_modes length must equal locations length minus one")

        session = SessionLocal()
        try:
            location_ids: list[int] = []
            for location_text in cleaned_locations:
                address = Address(raw_text=location_text, lat=0.0, lng=0.0)
                session.add(address)
                session.flush()
                location_ids.append(address.id)

            task = RouteTask(
                status=TaskStatus.PENDING,
                locations=location_ids,
                segment_modes=cleaned_modes,
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

    def get_cached_coordinates(self, address_text: str | None) -> dict | None:
        if not address_text or not address_text.strip():
            return None

        normalized = address_text.strip()
        session = SessionLocal()
        try:
            query = (
                select(Address)
                .where(
                    Address.raw_text == normalized,
                    or_(Address.lat != 0.0, Address.lng != 0.0),
                )
                .order_by(Address.id.desc())
                .limit(1)
            )
            address = session.execute(query).scalars().first()
            if not address:
                return None

            return {"lat": float(address.lat), "lng": float(address.lng)}
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

            locations = [int(location_id) for location_id in (task.locations or [])]
            addresses = session.execute(
                select(Address).where(Address.id.in_(locations))
            ).scalars().all() if locations else []
            address_by_id = {address.id: address for address in addresses}

            ordered_texts: list[str | None] = []
            for location_id in locations:
                address = address_by_id.get(location_id)
                ordered_texts.append(address.raw_text if address else None)
            mode, drive_part = self._derive_legacy_mode_fields(task.segment_modes or [])

            return {
                "task_id": str(task.id),
                "locations": locations,
                "location_texts": ordered_texts,
                "segment_modes": task.segment_modes or [],
                "start_text": ordered_texts[0] if len(ordered_texts) >= 1 else None,
                "transfer_text": ordered_texts[1] if len(ordered_texts) >= 3 else None,
                "destination_text": ordered_texts[-1] if ordered_texts else None,
                "drive_part": drive_part,
                "mode": mode,
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
        result_json: str,
        location_points: list[dict[str, float]] | None = None,
        start_lat: float | None = None,
        start_lng: float | None = None,
        destination_lat: float | None = None,
        destination_lng: float | None = None,
        transfer_lat: float | None = None,
        transfer_lng: float | None = None,
    ) -> None:
        session = SessionLocal()
        try:
            task = session.get(RouteTask, uuid.UUID(task_id))
            if not task:
                return

            location_ids = [int(location_id) for location_id in (task.locations or [])]
            addresses = session.execute(
                select(Address).where(Address.id.in_(location_ids))
            ).scalars().all() if location_ids else []
            address_by_id = {address.id: address for address in addresses}

            if location_ids and location_points and len(location_points) == len(location_ids):
                for index, location_id in enumerate(location_ids):
                    address = address_by_id.get(location_id)
                    point = location_points[index] or {}
                    if not address:
                        continue
                    lat = point.get("lat")
                    lng = point.get("lng")
                    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                        address.lat = float(lat)
                        address.lng = float(lng)
            elif location_ids:
                start_address = address_by_id.get(location_ids[0])
                if start_address and start_lat is not None and start_lng is not None:
                    start_address.lat = start_lat
                    start_address.lng = start_lng

                destination_address = address_by_id.get(location_ids[-1])
                if destination_address and destination_lat is not None and destination_lng is not None:
                    destination_address.lat = destination_lat
                    destination_address.lng = destination_lng

                if len(location_ids) >= 3 and transfer_lat is not None and transfer_lng is not None:
                    transfer_address = address_by_id.get(location_ids[1])
                    if transfer_address:
                        transfer_address.lat = transfer_lat
                        transfer_address.lng = transfer_lng

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
