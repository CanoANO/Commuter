from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Toronto"))


def _parse_duration_seconds(duration_str: str | None) -> int:
    if not duration_str or not isinstance(duration_str, str) or not duration_str.endswith("s"):
        return 0

    try:
        return int(float(duration_str[:-1]))
    except ValueError:
        return 0


def _parse_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None

    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_duration(seconds: int) -> str:
    safe_seconds = max(int(seconds), 0)
    hours = safe_seconds // 3600
    minutes = (safe_seconds % 3600) // 60
    remain = safe_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {remain}s"
    return f"{remain}s"


def _format_distance(meters: float | int | None) -> str:
    if not isinstance(meters, (int, float)):
        return "-"
    if meters < 1000:
        return f"{int(meters)} m"
    return f"{meters / 1000:.1f} km"


def _format_local_datetime(value: datetime | None) -> str:
    if not value:
        return "-"
    localized = value.astimezone(LOCAL_TZ)
    return localized.strftime("%Y-%m-%d %H:%M")


def _format_local_time_range(start: datetime | None, end: datetime | None) -> str:
    if not start and not end:
        return "-"
    return f"{_format_local_datetime(start)} → {_format_local_datetime(end)}"


def _build_segment_detail(segment: dict[str, Any]) -> dict[str, Any]:
    route = (segment.get("route") or {}).get("routes", [{}])[0]
    distance = route.get("distanceMeters")
    duration = route.get("duration")
    segment_seconds = _parse_duration_seconds(duration)

    legs = route.get("legs") if isinstance(route.get("legs"), list) else []
    timeline: list[dict[str, str]] = []

    total_walk_seconds = 0
    total_wait_seconds = 0
    total_transfer_seconds = 0
    total_transit_ride_seconds = 0

    first_departure: datetime | None = None
    last_arrival: datetime | None = None
    previous_transit_arrival: datetime | None = None
    transit_leg_count = 0

    elapsed_seconds = 0
    before_first_transit_seconds: int | None = None
    at_last_transit_end_seconds: int | None = None

    transit_steps_output: list[dict[str, Any]] = []

    for leg in legs:
        steps = leg.get("steps") if isinstance(leg.get("steps"), list) else []
        for step in steps:
            travel_mode = step.get("travelMode") or "UNKNOWN"
            seconds = _parse_duration_seconds(step.get("staticDuration") or step.get("duration"))
            instruction = (step.get("navigationInstruction") or {}).get("instructions") or ""

            if travel_mode == "TRANSIT" and step.get("transitDetails"):
                detail = step["transitDetails"]
                line = detail.get("transitLine") or {}
                stop_details = detail.get("stopDetails") or {}

                departure_dt = _parse_datetime(stop_details.get("departureTime"))
                arrival_dt = _parse_datetime(stop_details.get("arrivalTime"))

                if not first_departure and departure_dt:
                    first_departure = departure_dt
                if arrival_dt:
                    last_arrival = arrival_dt
                if before_first_transit_seconds is None and departure_dt:
                    before_first_transit_seconds = elapsed_seconds

                if previous_transit_arrival and departure_dt and departure_dt > previous_transit_arrival:
                    wait_seconds = int((departure_dt - previous_transit_arrival).total_seconds())
                    if wait_seconds > 0:
                        total_wait_seconds += wait_seconds
                        timeline.append(
                            {
                                "time_text": _format_local_time_range(previous_transit_arrival, departure_dt),
                                "label": f"Waiting {_format_duration(wait_seconds)}",
                            }
                        )

                if departure_dt and arrival_dt and arrival_dt > departure_dt:
                    ride_seconds = int((arrival_dt - departure_dt).total_seconds())
                else:
                    ride_seconds = seconds

                ride_seconds = max(ride_seconds, 0)
                total_transit_ride_seconds += ride_seconds
                transit_leg_count += 1
                previous_transit_arrival = arrival_dt or previous_transit_arrival
                at_last_transit_end_seconds = elapsed_seconds + seconds

                vehicle_name = (
                    ((line.get("vehicle") or {}).get("name") or {}).get("text")
                    or (line.get("vehicle") or {}).get("type")
                    or "Transit"
                )
                line_name = line.get("nameShort") or line.get("name") or detail.get("headsign") or "Line"
                departure_stop = ((stop_details.get("departureStop") or {}).get("name")) or "-"
                arrival_stop = ((stop_details.get("arrivalStop") or {}).get("name")) or "-"

                timeline.append(
                    {
                        "time_text": _format_local_time_range(departure_dt, arrival_dt),
                        "label": f"{vehicle_name} {line_name}: {departure_stop} → {arrival_stop} ({_format_duration(ride_seconds)})",
                    }
                )

                transit_steps_output.append(
                    {
                        "vehicle": vehicle_name,
                        "line": line_name,
                        "from_stop": departure_stop,
                        "to_stop": arrival_stop,
                        "departure_time": stop_details.get("departureTime"),
                        "arrival_time": stop_details.get("arrivalTime"),
                        "stop_count": detail.get("stopCount"),
                        "headsign": detail.get("headsign") or "-",
                    }
                )

                elapsed_seconds += seconds
                continue

            if travel_mode == "WALK":
                total_walk_seconds += seconds
                if transit_leg_count > 0:
                    total_transfer_seconds += seconds
                timeline.append(
                    {
                        "time_text": _format_duration(seconds),
                        "label": f"Walk{': ' + instruction if instruction else ''}",
                    }
                )
                elapsed_seconds += seconds
                continue

            timeline.append(
                {
                    "time_text": _format_duration(seconds),
                    "label": f"{travel_mode}{': ' + instruction if instruction else ''}",
                }
            )
            elapsed_seconds += seconds

    estimated_start: datetime | None = None
    estimated_end: datetime | None = None

    if first_departure and before_first_transit_seconds is not None:
        estimated_start = first_departure - timedelta(seconds=before_first_transit_seconds)

    if last_arrival and at_last_transit_end_seconds is not None:
        after_last_transit_seconds = max(segment_seconds - at_last_transit_end_seconds, 0)
        estimated_end = last_arrival + timedelta(seconds=after_last_transit_seconds)

    if not estimated_start and estimated_end and segment_seconds > 0:
        estimated_start = estimated_end - timedelta(seconds=segment_seconds)

    if not estimated_end and estimated_start and segment_seconds > 0:
        estimated_end = estimated_start + timedelta(seconds=segment_seconds)

    return {
        "from": segment.get("from") or "-",
        "to": segment.get("to") or "-",
        "travel_mode": segment.get("travel_mode") or "-",
        "distance_meters": distance,
        "distance_text": _format_distance(distance),
        "duration_seconds": segment_seconds,
        "duration_text": _format_duration(segment_seconds),
        "walk_seconds": total_walk_seconds,
        "walk_text": _format_duration(total_walk_seconds),
        "wait_seconds": total_wait_seconds,
        "wait_text": _format_duration(total_wait_seconds),
        "transfer_seconds": total_transfer_seconds,
        "transfer_text": _format_duration(total_transfer_seconds),
        "transit_ride_seconds": total_transit_ride_seconds,
        "transit_ride_text": _format_duration(total_transit_ride_seconds),
        "has_transit": len(transit_steps_output) > 0,
        "timeline": timeline,
        "transit_steps": transit_steps_output,
        "departure_time": estimated_start.isoformat() if estimated_start else None,
        "arrival_time": estimated_end.isoformat() if estimated_end else None,
    }


def _resolve_segment_schedule(
    segment_details: list[dict[str, Any]],
    requested_arrival: datetime | None,
    query_time: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if not segment_details:
        return None, None

    segment_count = len(segment_details)
    departures: list[datetime | None] = [
        _parse_datetime(item.get("departure_time")) for item in segment_details
    ]
    arrivals: list[datetime | None] = [
        _parse_datetime(item.get("arrival_time")) for item in segment_details
    ]
    durations = [max(int(item.get("duration_seconds") or 0), 0) for item in segment_details]
    has_known_anchor = any(value is not None for value in departures) or any(value is not None for value in arrivals)

    if requested_arrival and arrivals[-1] is None:
        arrivals[-1] = requested_arrival

    if query_time and departures[0] is None and not has_known_anchor:
        departures[0] = query_time

    max_rounds = max(segment_count * 3, 3)
    for _ in range(max_rounds):
        changed = False

        for index in range(segment_count):
            duration_seconds = durations[index]

            if departures[index] is not None and arrivals[index] is None and duration_seconds > 0:
                arrivals[index] = departures[index] + timedelta(seconds=duration_seconds)
                changed = True

            if arrivals[index] is not None and departures[index] is None and duration_seconds > 0:
                departures[index] = arrivals[index] - timedelta(seconds=duration_seconds)
                changed = True

        for index in range(1, segment_count):
            previous_arrival = arrivals[index - 1]
            current_departure = departures[index]

            if previous_arrival is not None and current_departure is None:
                departures[index] = previous_arrival
                changed = True

            if current_departure is not None and previous_arrival is None:
                arrivals[index - 1] = current_departure
                changed = True

        for index in range(segment_count - 2, -1, -1):
            next_departure = departures[index + 1]
            current_arrival = arrivals[index]

            if next_departure is not None and current_arrival is None:
                arrivals[index] = next_departure
                changed = True

            if current_arrival is not None and next_departure is None:
                departures[index + 1] = current_arrival
                changed = True

        if not changed:
            break

    for index, segment in enumerate(segment_details):
        segment["departure_time"] = departures[index].isoformat() if departures[index] else None
        segment["arrival_time"] = arrivals[index].isoformat() if arrivals[index] else None

    known_departures = [value for value in departures if value is not None]
    known_arrivals = [value for value in arrivals if value is not None]

    overall_departure = min(known_departures) if known_departures else None
    overall_arrival = max(known_arrivals) if known_arrivals else None

    return overall_departure, overall_arrival


def build_task_analysis(task_payload: dict[str, Any]) -> dict[str, Any]:
    result = task_payload.get("result") if isinstance(task_payload, dict) else None
    if not isinstance(result, dict):
        return {"summary": {}, "segments": []}

    segments = result.get("segments") if isinstance(result.get("segments"), list) else []

    segment_details = [_build_segment_detail(segment) for segment in segments]

    total_distance = sum(item.get("distance_meters") or 0 for item in segment_details)
    total_duration = sum(item.get("duration_seconds") or 0 for item in segment_details)
    total_walk = sum(item.get("walk_seconds") or 0 for item in segment_details)
    total_wait = sum(item.get("wait_seconds") or 0 for item in segment_details)
    total_transfer = sum(item.get("transfer_seconds") or 0 for item in segment_details)

    transit_lines: set[str] = set()
    total_transit_stops = 0

    for item in segment_details:
        for step in item.get("transit_steps", []):
            line = step.get("line")
            if isinstance(line, str) and line:
                transit_lines.add(line)
            stop_count = step.get("stop_count")
            if isinstance(stop_count, int):
                total_transit_stops += stop_count

    requested_arrival = _parse_datetime(task_payload.get("arrive_time"))
    query_time = _parse_datetime(task_payload.get("query_time"))

    overall_departure, overall_arrival = _resolve_segment_schedule(
        segment_details=segment_details,
        requested_arrival=requested_arrival,
        query_time=query_time,
    )

    if overall_departure is None and overall_arrival is not None and total_duration > 0:
        overall_departure = overall_arrival - timedelta(seconds=total_duration)

    if overall_arrival is None and overall_departure is not None and total_duration > 0:
        overall_arrival = overall_departure + timedelta(seconds=total_duration)

    summary = {
        "mode": (result.get("mode") or "-").upper(),
        "segments": len(segment_details),
        "total_distance_meters": total_distance,
        "total_distance_text": _format_distance(total_distance),
        "total_duration_seconds": total_duration,
        "total_duration_text": _format_duration(total_duration),
        "walk_seconds": total_walk,
        "walk_text": _format_duration(total_walk),
        "wait_seconds": total_wait,
        "wait_text": _format_duration(total_wait),
        "transfer_seconds": total_transfer,
        "transfer_text": _format_duration(total_transfer),
        "has_transit": len(transit_lines) > 0,
        "transit_lines": len(transit_lines),
        "transit_stops": total_transit_stops,
        "departure_time": overall_departure.isoformat() if overall_departure else None,
        "arrival_time": overall_arrival.isoformat() if overall_arrival else None,
    }

    return {
        "version": 2,
        "summary": summary,
        "segments": segment_details,
    }
