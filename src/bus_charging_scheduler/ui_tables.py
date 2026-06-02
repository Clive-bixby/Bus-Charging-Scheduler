from __future__ import annotations

import pandas as pd

from bus_charging_scheduler.models import Scenario, SchedulerOutput


def routes_table(scenario: Scenario) -> pd.DataFrame:
    rows = []
    for route in scenario.routes.values():
        for segment in route.segments:
            rows.append(
                {
                    "route_id": route.route_id,
                    "route_name": route.name,
                    "from": segment.from_stop,
                    "to": segment.to_stop,
                    "distance_km": segment.distance_km,
                }
            )
    return pd.DataFrame(rows)


def stations_table(scenario: Scenario) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station_id": station.station_id,
                "is_scheduling_station": station.is_scheduling_station,
                "charger_count": station.charger_count,
                "default_charge_minutes": station.default_charge_minutes,
            }
            for station in scenario.stations.values()
        ]
    )


def buses_table(scenario: Scenario) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bus_id": bus.bus_id,
                "operator_id": bus.operator_id,
                "direction": bus.direction,
                "route_id": bus.route_id,
                "departure_time": bus.departure_time,
                "departure_minute": bus.departure_minute,
                "battery_range_km": bus.battery_range_km,
                "initial_charge_km": bus.initial_charge_km,
                "priority": bus.priority,
            }
            for bus in scenario.buses
        ]
    )


def weights_table(scenario: Scenario) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "individual", "weight": scenario.weights.individual},
            {"metric": "operator", "weight": scenario.weights.operator},
            {"metric": "overall", "weight": scenario.weights.overall},
        ]
    )


def bus_timeline_table(output: SchedulerOutput) -> pd.DataFrame:
    rows = []
    for entry in output.bus_timelines:
        row = entry.__dict__.copy()
        row["time"] = _clock_time(entry.time_minute)
        rows.append(row)
    return pd.DataFrame(rows)


def station_order_table(output: SchedulerOutput) -> pd.DataFrame:
    rows = []
    for entry in output.station_charging_orders:
        row = entry.__dict__.copy()
        row["queue_arrival"] = _clock_time(entry.queue_arrival_minute)
        row["charge_start"] = _clock_time(entry.charge_start_minute)
        row["charge_end"] = _clock_time(entry.charge_end_minute)
        rows.append(row)
    return pd.DataFrame(rows)


def _clock_time(minute: float) -> str:
    total_minutes = int(round(minute)) % (24 * 60)
    hour = total_minutes // 60
    minute_part = total_minutes % 60
    return f"{hour:02d}:{minute_part:02d}"
