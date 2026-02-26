import os
import logging
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

class GoogleMapsService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
        logger.info("GoogleMapsService initialized api_key_present=%s", bool(self.api_key))

    def geocode_address(self, address: str) -> dict:
        if not self.api_key:
            logger.error("Geocode skipped: GOOGLE_MAPS_API_KEY is missing")
            return {}

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": self.api_key,
        }
        logger.info("Geocoding address='%s'", address)
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        status = data.get("status")
        if status != "OK" or not data.get("results"):
            logger.warning(
                "Geocode failed address='%s' status='%s' error='%s'",
                address,
                status,
                data.get("error_message"),
            )
            return {}
        location = data["results"][0]["geometry"]["location"]
        logger.info(
            "Geocode success address='%s' lat=%s lng=%s",
            address,
            location.get("lat"),
            location.get("lng"),
        )
        return {
            "lat": location.get("lat"),
            "lng": location.get("lng"),
        }

    @staticmethod
    def _normalize_time(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.now().astimezone().tzinfo).astimezone().isoformat()
            return value.astimezone().isoformat()
        if isinstance(value, str) and value.strip():
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
                return parsed.astimezone().isoformat()
            except ValueError:
                return value
        return None

    def compute_route(
        self,
        origin: dict,
        destination: dict,
        mode: str = "DRIVE",
        arrival_time=None,
        departure_time=None,
    ) -> dict:
        if not self.api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is missing")

        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        field_mask = ",".join([
            "routes.duration",
            "routes.distanceMeters",
            "routes.polyline.encodedPolyline",
            "routes.legs.distanceMeters",
            "routes.legs.duration",
            "routes.legs.steps.distanceMeters",
            "routes.legs.steps.staticDuration",
            "routes.legs.steps.travelMode",
            "routes.legs.steps.navigationInstruction.instructions",
            "routes.legs.steps.polyline.encodedPolyline",
            "routes.legs.steps.transitDetails.headsign",
            "routes.legs.steps.transitDetails.stopCount",
            "routes.legs.steps.transitDetails.stopDetails.arrivalStop.name",
            "routes.legs.steps.transitDetails.stopDetails.departureStop.name",
            "routes.legs.steps.transitDetails.stopDetails.arrivalTime",
            "routes.legs.steps.transitDetails.stopDetails.departureTime",
            "routes.legs.steps.transitDetails.transitLine.name",
            "routes.legs.steps.transitDetails.transitLine.nameShort",
            "routes.legs.steps.transitDetails.transitLine.vehicle.name.text",
            "routes.legs.steps.transitDetails.transitLine.vehicle.type",
        ])
        payload = {
            "origin": {"location": {"latLng": {"latitude": origin["lat"], "longitude": origin["lng"]}}},
            "destination": {"location": {"latLng": {"latitude": destination["lat"], "longitude": destination["lng"]}}},
            "travelMode": mode,
        }
        normalized_arrival_time = self._normalize_time(arrival_time)
        normalized_departure_time = self._normalize_time(departure_time)
        if mode == "TRANSIT":
            if normalized_arrival_time:
                payload["arrivalTime"] = normalized_arrival_time
            elif normalized_departure_time:
                payload["departureTime"] = normalized_departure_time

        logger.info(
            "Computing route mode=%s origin=(%s,%s) destination=(%s,%s) arrival_time=%s departure_time=%s",
            mode,
            origin.get("lat"),
            origin.get("lng"),
            destination.get("lat"),
            destination.get("lng"),
            normalized_arrival_time,
            normalized_departure_time,
        )
        fallback_field_mask = field_mask.replace("nameShort", "shortName")
        field_masks = [field_mask] if fallback_field_mask == field_mask else [field_mask, fallback_field_mask]

        result = None
        last_error = None
        for current_mask in field_masks:
            headers = {
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": current_mask,
            }
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.ok:
                result = response.json()
                break
            last_error = response

        if result is None:
            if last_error is not None:
                last_error.raise_for_status()
            raise RuntimeError("Failed to compute route")

        route_count = len(result.get("routes", [])) if isinstance(result, dict) else 0
        logger.info("Route compute success mode=%s routes=%s", mode, route_count)
        return result
