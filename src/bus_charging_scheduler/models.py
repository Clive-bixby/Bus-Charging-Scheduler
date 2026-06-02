from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    BUS_DEPARTURE = "BusDeparture"
    BUS_ARRIVE_STATION = "BusArriveStation"
    CHARGING_START = "ChargingStart"
    CHARGING_END = "ChargingEnd"
    BUS_ARRIVE_DESTINATION = "BusArriveDestination"


@dataclass(frozen=True)
class RouteSegment:
    from_stop: str
    to_stop: str
    distance_km: float


@dataclass(frozen=True)
class Route:
    route_id: str
    name: str
    ordered_stops: list[str]
    segments: list[RouteSegment]

    def stop_index(self, stop_id: str) -> int:
        return self.ordered_stops.index(stop_id)

    def segment_from_index(self, index: int) -> RouteSegment:
        from_stop = self.ordered_stops[index]
        to_stop = self.ordered_stops[index + 1]
        for segment in self.segments:
            if segment.from_stop == from_stop and segment.to_stop == to_stop:
                return segment
        raise ValueError(f"Missing segment from {from_stop} to {to_stop}")

    def distance_between_stops(self, from_stop: str, to_stop: str) -> float:
        start = self.stop_index(from_stop)
        end = self.stop_index(to_stop)
        if end <= start:
            raise ValueError(f"{to_stop} is not after {from_stop} on route {self.route_id}")
        return sum(self.segment_from_index(index).distance_km for index in range(start, end))

    @property
    def origin(self) -> str:
        return self.ordered_stops[0]

    @property
    def destination(self) -> str:
        return self.ordered_stops[-1]


@dataclass(frozen=True)
class Charger:
    station_id: str
    charger_id: int


@dataclass(frozen=True)
class Station:
    station_id: str
    is_scheduling_station: bool
    charger_count: int = 1
    default_charge_minutes: float = 25.0
    outage_windows: list[dict[str, Any]] = field(default_factory=list)
    pricing: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Bus:
    bus_id: str
    operator_id: str
    route_id: str
    departure_minute: float
    battery_range_km: float
    initial_charge_km: float
    direction: str | None = None
    departure_time: str | None = None
    priority: float = 1.0
    driver_shift: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Weights:
    individual: float
    operator: float
    overall: float


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    average_speed_kmph: float
    routes: dict[str, Route]
    stations: dict[str, Station]
    buses: list[Bus]
    weights: Weights
    scheduler: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationEvent:
    time_minute: float
    priority: int
    sequence: int
    event_type: EventType
    bus_id: str
    station_id: str | None = None
    charger_id: int | None = None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SimulationEvent):
            return NotImplemented
        return (
            self.time_minute,
            self.priority,
            self.sequence,
        ) < (
            other.time_minute,
            other.priority,
            other.sequence,
        )


class BusDeparture(SimulationEvent):
    def __init__(self, time_minute: float, sequence: int, bus_id: str) -> None:
        super().__init__(time_minute, 10, sequence, EventType.BUS_DEPARTURE, bus_id)


class BusArriveStation(SimulationEvent):
    def __init__(self, time_minute: float, sequence: int, bus_id: str, station_id: str) -> None:
        super().__init__(
            time_minute,
            20,
            sequence,
            EventType.BUS_ARRIVE_STATION,
            bus_id,
            station_id,
        )


class ChargingStart(SimulationEvent):
    def __init__(
        self,
        time_minute: float,
        sequence: int,
        bus_id: str,
        station_id: str,
        charger_id: int,
    ) -> None:
        super().__init__(
            time_minute,
            30,
            sequence,
            EventType.CHARGING_START,
            bus_id,
            station_id,
            charger_id,
        )


class ChargingEnd(SimulationEvent):
    def __init__(
        self,
        time_minute: float,
        sequence: int,
        bus_id: str,
        station_id: str,
        charger_id: int,
    ) -> None:
        super().__init__(
            time_minute,
            40,
            sequence,
            EventType.CHARGING_END,
            bus_id,
            station_id,
            charger_id,
        )


class BusArriveDestination(SimulationEvent):
    def __init__(self, time_minute: float, sequence: int, bus_id: str, station_id: str) -> None:
        super().__init__(
            time_minute,
            50,
            sequence,
            EventType.BUS_ARRIVE_DESTINATION,
            bus_id,
            station_id,
        )


@dataclass
class TimelineEntry:
    bus_id: str
    operator_id: str
    event: str
    station_id: str
    time_minute: float
    battery_km: float
    charger_id: int | None = None
    wait_minutes: float = 0.0


@dataclass
class ChargingOrderEntry:
    station_id: str
    charger_id: int
    order: int
    bus_id: str
    operator_id: str
    queue_arrival_minute: float
    charge_start_minute: float
    charge_end_minute: float
    wait_minutes: float


@dataclass
class SchedulerOutput:
    scenario_id: str
    bus_timelines: list[TimelineEntry]
    station_charging_orders: list[ChargingOrderEntry]
    summary_metrics: dict[str, Any]
    rule_violations: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "bus_timelines": [entry.__dict__ for entry in self.bus_timelines],
            "station_charging_orders": [entry.__dict__ for entry in self.station_charging_orders],
            "summary_metrics": self.summary_metrics,
            "rule_violations": self.rule_violations,
        }
