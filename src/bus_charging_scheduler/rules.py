from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from bus_charging_scheduler.models import Bus, Route, Scenario, SimulationEvent, Station


@dataclass(frozen=True)
class RuleContext:
    scenario: Scenario
    event: SimulationEvent | None = None
    bus: Bus | None = None
    route: Route | None = None
    station: Station | None = None
    state: Any | None = None
    from_stop: str | None = None
    to_stop: str | None = None
    distance_km: float | None = None
    battery_km: float | None = None
    charger_id: int | None = None


@dataclass(frozen=True)
class RuleResult:
    rule_name: str
    valid: bool
    message: str = ""


class Rule(Protocol):
    name: str

    def validate(self, context: RuleContext) -> RuleResult:
        ...


class RangeRule:
    name = "RangeRule"

    def validate(self, context: RuleContext) -> RuleResult:
        if context.distance_km is None or context.battery_km is None:
            return RuleResult(self.name, True)
        valid = context.distance_km <= context.battery_km + 1e-9
        message = "" if valid else (
            f"distance {context.distance_km:.1f} km exceeds available battery "
            f"{context.battery_km:.1f} km"
        )
        return RuleResult(self.name, valid, message)


class ChargerCapacityRule:
    name = "ChargerCapacityRule"

    def validate(self, context: RuleContext) -> RuleResult:
        if context.station is None or context.state is None:
            return RuleResult(self.name, True)
        station_state = context.state.station_runtimes.get(context.station.station_id)
        if station_state is None:
            return RuleResult(self.name, True)
        valid = len(station_state.busy_chargers) <= context.station.charger_count
        if context.charger_id is not None:
            valid = valid and 0 <= context.charger_id < context.station.charger_count
        message = "" if valid else f"station {context.station.station_id} exceeded charger capacity"
        return RuleResult(self.name, valid, message)


class RouteOrderRule:
    name = "RouteOrderRule"

    def validate(self, context: RuleContext) -> RuleResult:
        if context.route is None or context.from_stop is None or context.to_stop is None:
            return RuleResult(self.name, True)
        from_index = context.route.stop_index(context.from_stop)
        to_index = context.route.stop_index(context.to_stop)
        valid = to_index > from_index
        message = "" if valid else f"route order violation: {context.from_stop} -> {context.to_stop}"
        return RuleResult(self.name, valid, message)


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules = rules or [RangeRule(), ChargerCapacityRule(), RouteOrderRule()]

    def validate(self, context: RuleContext) -> list[RuleResult]:
        return [rule.validate(context) for rule in self.rules]

    def validate_or_raise(self, context: RuleContext) -> None:
        failures = [result for result in self.validate(context) if not result.valid]
        if failures:
            joined = "; ".join(f"{failure.rule_name}: {failure.message}" for failure in failures)
            raise ValueError(joined)
