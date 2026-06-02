from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bus_charging_scheduler.models import Bus, Weights


@dataclass(frozen=True)
class ScoreBreakdown:
    bus_id: str
    individual_metric: float
    operator_metric: float
    overall_metric: float
    total: float


class ScoringEngine:
    def __init__(self, weights: Weights) -> None:
        self.weights = weights

    def queue_score(
        self,
        bus: Bus,
        current_time: float,
        waiting_since: float,
        state: Any,
    ) -> ScoreBreakdown:
        # Individual objective: a bus that has already waited longer should
        # move up the queue, preventing one bus from absorbing too much delay.
        wait_minutes = max(0.0, current_time - waiting_since)

        # Operator fairness objective: prioritize operators that have actually
        # experienced higher average waiting time, not merely fewer sessions.
        operator_avg_wait = self._get_operator_average_wait(bus.operator_id, state)
        max_operator_avg_wait = self._get_max_operator_average_wait(state)
        operator_metric = (
            operator_avg_wait
            if max_operator_avg_wait > 0
            else self._get_cold_start_operator_balance(bus.operator_id, state)
        )

        # Network efficiency objective: a congested station is already costly
        # for the whole network, so additional demand there lowers the score.
        overall_metric = -self._get_station_congestion(bus, waiting_since, state)

        total = (
            self.weights.individual * wait_minutes
            + self.weights.operator * operator_metric
            + self.weights.overall * overall_metric
        )
        return ScoreBreakdown(
            bus_id=bus.bus_id,
            individual_metric=wait_minutes,
            operator_metric=operator_metric,
            overall_metric=overall_metric,
            total=total,
        )

    def plan_score(self, bus: Bus, plan: tuple[str, ...], state: Any) -> float:
        station_load = sum(
            state.station_planned_load.get(station_id, 0)
            for station_id in plan
        )
        operator_station_load = sum(
            state.operator_planned_counts.get((bus.operator_id, station_id), 0)
            for station_id in plan
        )

        # Individual objective: fewer stops generally means less interruption
        # for a single bus, while still respecting hard range constraints.
        individual_metric = -float(len(plan))

        # Operator fairness objective: avoid repeatedly sending one operator's
        # buses to the same stations and creating localized operator delays.
        operator_metric = -float(operator_station_load)

        # Network efficiency objective: avoid charge plans that concentrate
        # demand at stations already selected by earlier buses.
        overall_metric = -float(station_load)

        return (
            self.weights.individual * individual_metric
            + self.weights.operator * operator_metric
            + self.weights.overall * overall_metric
        )

    def _get_operator_average_wait(self, operator_id: str, state: Any) -> float:
        operator_wait_totals = self._get_operator_wait_totals(state)
        operator_charge_counts = getattr(state, "operator_charge_counts", {})
        total_wait = operator_wait_totals.get(operator_id, 0.0)
        charge_count = operator_charge_counts.get(operator_id, 0)
        return total_wait / max(1, charge_count)

    def _get_max_operator_average_wait(self, state: Any) -> float:
        operator_ids = set(getattr(state, "operator_charge_counts", {}).keys())
        operator_wait_totals = self._get_operator_wait_totals(state)
        operator_ids.update(operator_wait_totals.keys())
        if not operator_ids:
            return 0.0
        return max(self._get_operator_average_wait(operator_id, state) for operator_id in operator_ids)

    def _get_station_congestion(self, bus: Bus, waiting_since: float, state: Any) -> float:
        station_runtimes = getattr(state, "station_runtimes", {})
        for station_state in station_runtimes.values():
            for queued_bus in getattr(station_state, "waiting_heap", []):
                if queued_bus.bus_id == bus.bus_id and queued_bus.waiting_since == waiting_since:
                    queue_length = len(station_state.waiting_heap)
                    busy_chargers = len(station_state.busy_chargers)
                    return float(queue_length + busy_chargers)
        return 0.0

    def _get_operator_wait_totals(self, state: Any) -> dict[str, float]:
        wait_totals: dict[str, float] = {}
        for station_orders in getattr(state, "station_orders", {}).values():
            for entry in station_orders:
                wait_totals[entry.operator_id] = wait_totals.get(entry.operator_id, 0.0) + entry.wait_minutes
        return wait_totals

    def _get_cold_start_operator_balance(self, operator_id: str, state: Any) -> float:
        operator_charge_counts = getattr(state, "operator_charge_counts", {})
        max_charge_count = max(operator_charge_counts.values(), default=0)
        return float(max_charge_count - operator_charge_counts.get(operator_id, 0))
