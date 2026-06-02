from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import count

from bus_charging_scheduler.models import (
    Bus,
    BusArriveDestination,
    BusArriveStation,
    BusDeparture,
    ChargingEnd,
    ChargingOrderEntry,
    ChargingStart,
    EventType,
    Scenario,
    SchedulerOutput,
    SimulationEvent,
    TimelineEntry,
)
from bus_charging_scheduler.output import build_summary_metrics
from bus_charging_scheduler.rules import RuleContext, RuleEngine
from bus_charging_scheduler.scheduler import GreedyWeightedScheduler, QueuedBus
from bus_charging_scheduler.scoring import ScoringEngine


@dataclass
class BusRuntime:
    bus_id: str
    current_stop_index: int = 0
    battery_km: float = 0.0
    planned_charge_stops: list[str] = field(default_factory=list)
    next_charge_index: int = 0
    last_station_arrival_minute: float = 0.0
    complete: bool = False


@dataclass
class ChargingSession:
    bus_id: str
    charger_id: int
    queue_arrival_minute: float
    charge_start_minute: float


@dataclass
class StationRuntime:
    station_id: str
    available_chargers: list[int]
    busy_chargers: dict[int, str] = field(default_factory=dict)
    waiting_heap: list[QueuedBus] = field(default_factory=list)
    active_sessions: dict[int, ChargingSession] = field(default_factory=dict)
    order_counter: int = 0


@dataclass
class SchedulerState:
    scenario: Scenario
    buses: dict[str, Bus]
    bus_runtimes: dict[str, BusRuntime]
    station_runtimes: dict[str, StationRuntime]
    timelines: dict[str, list[TimelineEntry]] = field(default_factory=dict)
    station_orders: dict[str, list[ChargingOrderEntry]] = field(default_factory=dict)
    rule_violations: list[dict[str, object]] = field(default_factory=list)
    operator_charge_counts: dict[str, int] = field(default_factory=dict)
    station_planned_load: dict[str, int] = field(default_factory=dict)
    operator_planned_counts: dict[tuple[str, str], int] = field(default_factory=dict)


class SimulationEngine:
    def __init__(
        self,
        scenario: Scenario,
        rule_engine: RuleEngine | None = None,
        scheduler: GreedyWeightedScheduler | None = None,
    ) -> None:
        self.scenario = scenario
        self.rule_engine = rule_engine or RuleEngine()
        self.scoring_engine = ScoringEngine(scenario.weights)
        self.scheduler = scheduler or GreedyWeightedScheduler(scenario, self.scoring_engine)
        self._sequence = count()
        self._event_queue: list[SimulationEvent] = []
        self.state = self._build_initial_state()

    def run(self) -> SchedulerOutput:
        for bus in self.scenario.buses:
            self._push(BusDeparture(bus.departure_minute, next(self._sequence), bus.bus_id))
        while self._event_queue:
            event = heapq.heappop(self._event_queue)
            self._process_event(event)
        bus_timelines = [
            entry
            for bus_id in sorted(self.state.timelines)
            for entry in self.state.timelines[bus_id]
        ]
        station_orders = [
            entry
            for station_id in sorted(self.state.station_orders)
            for entry in self.state.station_orders[station_id]
        ]
        return SchedulerOutput(
            scenario_id=self.scenario.scenario_id,
            bus_timelines=bus_timelines,
            station_charging_orders=station_orders,
            summary_metrics=build_summary_metrics(bus_timelines, station_orders),
            rule_violations=self.state.rule_violations,
        )

    def _build_initial_state(self) -> SchedulerState:
        buses = {bus.bus_id: bus for bus in self.scenario.buses}
        bus_runtimes = {
            bus.bus_id: BusRuntime(bus_id=bus.bus_id, battery_km=bus.initial_charge_km)
            for bus in self.scenario.buses
        }
        station_runtimes = {
            station_id: StationRuntime(station_id, list(range(station.charger_count)))
            for station_id, station in self.scenario.stations.items()
        }
        return SchedulerState(
            scenario=self.scenario,
            buses=buses,
            bus_runtimes=bus_runtimes,
            station_runtimes=station_runtimes,
            timelines={bus.bus_id: [] for bus in self.scenario.buses},
            station_orders={station_id: [] for station_id in self.scenario.stations},
            operator_charge_counts={bus.operator_id: 0 for bus in self.scenario.buses},
        )

    def _push(self, event: SimulationEvent) -> None:
        heapq.heappush(self._event_queue, event)

    def _process_event(self, event: SimulationEvent) -> None:
        if event.event_type == EventType.BUS_DEPARTURE:
            self._handle_departure(event)
        elif event.event_type == EventType.BUS_ARRIVE_STATION:
            self._handle_arrival(event)
        elif event.event_type == EventType.CHARGING_START:
            self._handle_charging_start(event)
        elif event.event_type == EventType.CHARGING_END:
            self._handle_charging_end(event)
        elif event.event_type == EventType.BUS_ARRIVE_DESTINATION:
            self._handle_destination(event)

    def _handle_departure(self, event: SimulationEvent) -> None:
        bus = self.state.buses[event.bus_id]
        runtime = self.state.bus_runtimes[event.bus_id]
        runtime.planned_charge_stops = self.scheduler.choose_charge_plan(bus, self.state)
        self._record_timeline(event.bus_id, "departure", self.scenario.routes[bus.route_id].origin, event.time_minute)
        self._schedule_next_arrival(event.bus_id, event.time_minute)

    def _handle_arrival(self, event: SimulationEvent) -> None:
        bus = self.state.buses[event.bus_id]
        route = self.scenario.routes[bus.route_id]
        runtime = self.state.bus_runtimes[event.bus_id]
        segment = route.segment_from_index(runtime.current_stop_index)
        runtime.battery_km -= segment.distance_km
        runtime.current_stop_index += 1
        runtime.last_station_arrival_minute = event.time_minute
        station_id = route.ordered_stops[runtime.current_stop_index]
        self._record_timeline(event.bus_id, "arrive_station", station_id, event.time_minute)
        if station_id == route.destination:
            self._push(BusArriveDestination(event.time_minute, next(self._sequence), event.bus_id, station_id))
            return
        if self._should_charge(event.bus_id, station_id):
            self._request_charging(event.bus_id, station_id, event.time_minute)
            return
        self._schedule_next_arrival(event.bus_id, event.time_minute)

    def _handle_charging_start(self, event: SimulationEvent) -> None:
        if event.station_id is None or event.charger_id is None:
            raise ValueError("ChargingStart requires station_id and charger_id")
        station = self.scenario.stations[event.station_id]
        station_state = self.state.station_runtimes[event.station_id]
        bus = self.state.buses[event.bus_id]
        runtime = self.state.bus_runtimes[event.bus_id]
        queue_arrival = runtime.last_station_arrival_minute
        station_state.busy_chargers[event.charger_id] = event.bus_id
        station_state.active_sessions[event.charger_id] = ChargingSession(
            bus_id=event.bus_id,
            charger_id=event.charger_id,
            queue_arrival_minute=queue_arrival,
            charge_start_minute=event.time_minute,
        )
        self.state.operator_charge_counts[bus.operator_id] = self.state.operator_charge_counts.get(bus.operator_id, 0) + 1
        self._validate_and_record(
            RuleContext(
                scenario=self.scenario,
                event=event,
                bus=bus,
                station=station,
                state=self.state,
                charger_id=event.charger_id,
            )
        )
        self._record_timeline(
            event.bus_id,
            "charge_start",
            event.station_id,
            event.time_minute,
            charger_id=event.charger_id,
            wait_minutes=event.time_minute - queue_arrival,
        )
        end_time = event.time_minute + station.default_charge_minutes
        self._push(ChargingEnd(end_time, next(self._sequence), event.bus_id, event.station_id, event.charger_id))

    def _handle_charging_end(self, event: SimulationEvent) -> None:
        if event.station_id is None or event.charger_id is None:
            raise ValueError("ChargingEnd requires station_id and charger_id")
        bus = self.state.buses[event.bus_id]
        station_state = self.state.station_runtimes[event.station_id]
        station = self.scenario.stations[event.station_id]
        runtime = self.state.bus_runtimes[event.bus_id]
        session = station_state.active_sessions.pop(event.charger_id)
        station_state.busy_chargers.pop(event.charger_id)
        station_state.available_chargers.append(event.charger_id)
        station_state.available_chargers.sort()
        station_state.order_counter += 1
        runtime.battery_km = bus.battery_range_km
        if runtime.next_charge_index < len(runtime.planned_charge_stops):
            runtime.next_charge_index += 1
        wait = session.charge_start_minute - session.queue_arrival_minute
        self.state.station_orders[event.station_id].append(
            ChargingOrderEntry(
                station_id=event.station_id,
                charger_id=event.charger_id,
                order=station_state.order_counter,
                bus_id=event.bus_id,
                operator_id=bus.operator_id,
                queue_arrival_minute=session.queue_arrival_minute,
                charge_start_minute=session.charge_start_minute,
                charge_end_minute=event.time_minute,
                wait_minutes=wait,
            )
        )
        self._record_timeline(event.bus_id, "charge_end", event.station_id, event.time_minute, charger_id=event.charger_id)
        self._validate_and_record(
            RuleContext(
                scenario=self.scenario,
                event=event,
                bus=bus,
                station=station,
                state=self.state,
                charger_id=event.charger_id,
            )
        )
        self._start_next_waiting_bus(event.station_id, event.time_minute)
        self._schedule_next_arrival(event.bus_id, event.time_minute)

    def _handle_destination(self, event: SimulationEvent) -> None:
        runtime = self.state.bus_runtimes[event.bus_id]
        runtime.complete = True
        station_id = event.station_id or ""
        self._record_timeline(event.bus_id, "arrive_destination", station_id, event.time_minute)

    def _schedule_next_arrival(self, bus_id: str, current_time: float) -> None:
        bus = self.state.buses[bus_id]
        route = self.scenario.routes[bus.route_id]
        runtime = self.state.bus_runtimes[bus_id]
        if runtime.current_stop_index >= len(route.ordered_stops) - 1:
            return
        segment = route.segment_from_index(runtime.current_stop_index)
        self._validate_and_record(
            RuleContext(
                scenario=self.scenario,
                bus=bus,
                route=route,
                state=self.state,
                from_stop=segment.from_stop,
                to_stop=segment.to_stop,
                distance_km=segment.distance_km,
                battery_km=runtime.battery_km,
            )
        )
        travel_minutes = segment.distance_km / self.scenario.average_speed_kmph * 60
        next_stop = segment.to_stop
        self._push(BusArriveStation(current_time + travel_minutes, next(self._sequence), bus_id, next_stop))

    def _should_charge(self, bus_id: str, station_id: str) -> bool:
        runtime = self.state.bus_runtimes[bus_id]
        if runtime.next_charge_index >= len(runtime.planned_charge_stops):
            return False
        return runtime.planned_charge_stops[runtime.next_charge_index] == station_id

    def _request_charging(self, bus_id: str, station_id: str, current_time: float) -> None:
        station_state = self.state.station_runtimes[station_id]
        if station_state.available_chargers and not station_state.waiting_heap:
            charger_id = station_state.available_chargers.pop(0)
            self._push(ChargingStart(current_time, next(self._sequence), bus_id, station_id, charger_id))
            return
        self.scheduler.enqueue_waiting_bus(station_id, bus_id, current_time, next(self._sequence), self.state)

    def _start_next_waiting_bus(self, station_id: str, current_time: float) -> None:
        station_state = self.state.station_runtimes[station_id]
        while station_state.available_chargers and station_state.waiting_heap:
            queued = self.scheduler.pop_next_waiting_bus(station_id, current_time, self.state)
            if queued is None:
                return
            charger_id = station_state.available_chargers.pop(0)
            self._push(ChargingStart(current_time, next(self._sequence), queued.bus_id, station_id, charger_id))

    def _record_timeline(
        self,
        bus_id: str,
        event_name: str,
        station_id: str,
        time_minute: float,
        charger_id: int | None = None,
        wait_minutes: float = 0.0,
    ) -> None:
        bus = self.state.buses[bus_id]
        runtime = self.state.bus_runtimes[bus_id]
        self.state.timelines[bus_id].append(
            TimelineEntry(
                bus_id=bus_id,
                operator_id=bus.operator_id,
                event=event_name,
                station_id=station_id,
                time_minute=round(time_minute, 2),
                battery_km=round(runtime.battery_km, 2),
                charger_id=charger_id,
                wait_minutes=round(wait_minutes, 2),
            )
        )

    def _validate_and_record(self, context: RuleContext) -> None:
        for result in self.rule_engine.validate(context):
            if not result.valid:
                self.state.rule_violations.append(
                    {
                        "rule": result.rule_name,
                        "message": result.message,
                        "bus_id": context.bus.bus_id if context.bus else None,
                        "event": context.event.event_type if context.event else None,
                    }
                )
                raise ValueError(f"{result.rule_name}: {result.message}")
