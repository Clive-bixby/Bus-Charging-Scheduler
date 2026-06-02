from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bus_charging_scheduler.models import Bus, Route, RouteSegment, Scenario, Station, Weights


def list_scenarios(scenarios_dir: Path) -> list[Path]:
    return sorted(scenarios_dir.glob("*.json"))


def load_scenario(path: Path) -> Scenario:
    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    return parse_scenario(raw)


def parse_scenario(raw: dict[str, Any]) -> Scenario:
    routes = {
        item["route_id"]: Route(
            route_id=item["route_id"],
            name=item.get("name", item["route_id"]),
            ordered_stops=list(item["ordered_stops"]),
            segments=[
                RouteSegment(
                    from_stop=segment["from"],
                    to_stop=segment["to"],
                    distance_km=float(segment["distance_km"]),
                )
                for segment in item["segments"]
            ],
        )
        for item in raw["routes"]
    }
    stations = {
        item["station_id"]: Station(
            station_id=item["station_id"],
            is_scheduling_station=bool(item.get("is_scheduling_station", True)),
            charger_count=int(item.get("charger_count", 1)),
            default_charge_minutes=float(item.get("default_charge_minutes", 25)),
            outage_windows=list(item.get("outage_windows", [])),
            pricing=dict(item.get("pricing", {})),
            metadata=dict(item.get("metadata", {})),
        )
        for item in raw["stations"]
    }
    buses = [
        Bus(
            bus_id=item["bus_id"],
            operator_id=item["operator_id"],
            route_id=item["route_id"],
            departure_minute=_parse_departure_minute(item),
            battery_range_km=float(item.get("battery_range_km", 240)),
            initial_charge_km=float(item.get("initial_charge_km", item.get("battery_range_km", 240))),
            direction=item.get("direction"),
            departure_time=item.get("departure_time"),
            priority=float(item.get("priority", 1)),
            driver_shift=item.get("driver_shift"),
            metadata=dict(item.get("metadata", {})),
        )
        for item in raw["buses"]
    ]
    weights_raw = raw["weights"]
    weights = Weights(
        individual=float(weights_raw["individual"]),
        operator=float(weights_raw["operator"]),
        overall=float(weights_raw["overall"]),
    )
    scenario = Scenario(
        scenario_id=raw["scenario_id"],
        name=raw.get("name", raw["scenario_id"]),
        average_speed_kmph=float(raw["average_speed_kmph"]),
        routes=routes,
        stations=stations,
        buses=buses,
        weights=weights,
        scheduler=dict(raw.get("scheduler", {})),
        metadata=dict(raw.get("metadata", {})),
    )
    _validate_scenario(scenario)
    return scenario


def _validate_scenario(scenario: Scenario) -> None:
    if scenario.average_speed_kmph <= 0:
        raise ValueError("average_speed_kmph must be positive")
    if not scenario.routes:
        raise ValueError("scenario must include at least one route")
    if not scenario.buses:
        raise ValueError("scenario must include at least one bus")
    for route in scenario.routes.values():
        expected_pairs = set(zip(route.ordered_stops, route.ordered_stops[1:]))
        segment_pairs = {(segment.from_stop, segment.to_stop) for segment in route.segments}
        missing = expected_pairs - segment_pairs
        if missing:
            raise ValueError(f"route {route.route_id} is missing segments: {sorted(missing)}")
    for station in scenario.stations.values():
        if station.charger_count < 0:
            raise ValueError(f"station {station.station_id} charger_count cannot be negative")
        if station.default_charge_minutes <= 0:
            raise ValueError(f"station {station.station_id} charge time must be positive")
    for bus in scenario.buses:
        if bus.route_id not in scenario.routes:
            raise ValueError(f"bus {bus.bus_id} references unknown route {bus.route_id}")
        if bus.initial_charge_km > bus.battery_range_km:
            raise ValueError(f"bus {bus.bus_id} initial_charge_km exceeds battery_range_km")


def _parse_departure_minute(item: dict[str, Any]) -> float:
    if "departure_minute" in item:
        return float(item["departure_minute"])
    if "departure_time" not in item:
        return 0.0
    hour_text, minute_text = str(item["departure_time"]).split(":", maxsplit=1)
    return float(int(hour_text) * 60 + int(minute_text))
