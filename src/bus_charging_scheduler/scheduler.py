from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

from bus_charging_scheduler.models import Bus, Route, Scenario
from bus_charging_scheduler.scoring import ScoringEngine


@dataclass(order=True)
class QueuedBus:
    priority: float
    waiting_since: float
    sequence: int
    bus_id: str = field(compare=False)


class GreedyWeightedScheduler:
    def __init__(self, scenario: Scenario, scoring_engine: ScoringEngine) -> None:
        self.scenario = scenario
        self.scoring_engine = scoring_engine

    def choose_charge_plan(self, bus: Bus, state: object) -> list[str]:
        route = self.scenario.routes[bus.route_id]
        feasible_plans = self._minimum_feasible_plans(bus, route)
        if not feasible_plans:
            raise ValueError(f"no feasible charging plan for bus {bus.bus_id}")
        chosen = max(
            feasible_plans,
            key=lambda plan: (
                self.scoring_engine.plan_score(bus, plan, state),
                tuple(reversed(plan)),
            ),
        )
        for station_id in chosen:
            state.station_planned_load[station_id] = state.station_planned_load.get(station_id, 0) + 1
            key = (bus.operator_id, station_id)
            state.operator_planned_counts[key] = state.operator_planned_counts.get(key, 0) + 1
        return list(chosen)

    def enqueue_waiting_bus(
        self,
        station_id: str,
        bus_id: str,
        waiting_since: float,
        sequence: int,
        state: object,
    ) -> None:
        station_state = state.station_runtimes[station_id]
        heapq.heappush(station_state.waiting_heap, QueuedBus(0.0, waiting_since, sequence, bus_id))

    def pop_next_waiting_bus(self, station_id: str, current_time: float, state: object) -> QueuedBus | None:
        station_state = state.station_runtimes[station_id]
        if not station_state.waiting_heap:
            return None
        rebuilt: list[QueuedBus] = []
        for queued in station_state.waiting_heap:
            bus = state.buses[queued.bus_id]
            score = self.scoring_engine.queue_score(bus, current_time, queued.waiting_since, state)
            heapq.heappush(
                rebuilt,
                QueuedBus(
                    priority=-score.total,
                    waiting_since=queued.waiting_since,
                    sequence=queued.sequence,
                    bus_id=queued.bus_id,
                ),
            )
        station_state.waiting_heap = rebuilt
        return heapq.heappop(station_state.waiting_heap)

    def _minimum_feasible_plans(self, bus: Bus, route: Route) -> list[tuple[str, ...]]:
        scheduling_stops = [
            stop
            for stop in route.ordered_stops[1:-1]
            if self.scenario.stations.get(stop) is not None
            and self.scenario.stations[stop].is_scheduling_station
            and self.scenario.stations[stop].charger_count > 0
        ]
        for count in range(len(scheduling_stops) + 1):
            plans = [
                plan
                for plan in itertools.combinations(scheduling_stops, count)
                if self._is_plan_feasible(bus, route, plan)
            ]
            if plans:
                return plans
        return []

    def _is_plan_feasible(self, bus: Bus, route: Route, plan: tuple[str, ...]) -> bool:
        checkpoints = [route.origin, *plan, route.destination]
        available_range = bus.initial_charge_km
        for start, end in zip(checkpoints, checkpoints[1:]):
            distance = route.distance_between_stops(start, end)
            if distance > available_range + 1e-9:
                return False
            available_range = bus.battery_range_km
        return True
