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
        wait_minutes = max(0.0, current_time - waiting_since)
        operator_counts = state.operator_charge_counts
        max_served = max(operator_counts.values(), default=0)
        operator_metric = max_served - operator_counts.get(bus.operator_id, 0)
        overall_metric = bus.priority
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
        operator_load = sum(state.operator_planned_counts.get((bus.operator_id, station_id), 0) for station_id in plan)
        station_load = sum(state.station_planned_load.get(station_id, 0) for station_id in plan)
        individual_metric = -float(len(plan))
        operator_metric = -float(operator_load)
        overall_metric = -float(station_load)
        return (
            self.weights.individual * individual_metric
            + self.weights.operator * operator_metric
            + self.weights.overall * overall_metric
        )
