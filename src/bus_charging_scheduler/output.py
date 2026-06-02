from __future__ import annotations

from statistics import mean

from bus_charging_scheduler.models import ChargingOrderEntry, TimelineEntry


def build_summary_metrics(
    timelines: list[TimelineEntry],
    station_orders: list[ChargingOrderEntry],
) -> dict[str, float | int]:
    waits = [entry.wait_minutes for entry in station_orders]
    destination_times = [
        entry.time_minute for entry in timelines if entry.event == "arrive_destination"
    ]
    return {
        "bus_count": len({entry.bus_id for entry in timelines}),
        "charge_count": len(station_orders),
        "average_wait_minutes": round(mean(waits), 2) if waits else 0.0,
        "max_wait_minutes": round(max(waits), 2) if waits else 0.0,
        "average_destination_minute": round(mean(destination_times), 2) if destination_times else 0.0,
        "latest_destination_minute": round(max(destination_times), 2) if destination_times else 0.0,
    }
