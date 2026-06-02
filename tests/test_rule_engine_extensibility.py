from bus_charging_scheduler.rules import RuleContext, RuleEngine, RuleResult
from bus_charging_scheduler.scenario_loader import parse_scenario
from bus_charging_scheduler.simulation import SimulationEngine


class DummyRule:
    name = "DummyRule"

    def validate(self, context: RuleContext) -> RuleResult:
        return RuleResult(self.name, True)


def test_custom_rule_can_be_registered_without_engine_changes() -> None:
    output = SimulationEngine(_scenario(), rule_engine=RuleEngine([DummyRule()])).run()

    assert output.rule_violations == []
    assert output.summary_metrics["bus_count"] == 1


def _scenario():
    return parse_scenario(
        {
            "scenario_id": "dummy_rule_test",
            "average_speed_kmph": 60,
            "routes": [
                {
                    "route_id": "r1",
                    "ordered_stops": ["Start", "A", "End"],
                    "segments": [
                        {"from": "Start", "to": "A", "distance_km": 100},
                        {"from": "A", "to": "End", "distance_km": 100},
                    ],
                }
            ],
            "stations": [
                {
                    "station_id": "A",
                    "is_scheduling_station": True,
                    "charger_count": 1,
                    "default_charge_minutes": 25,
                }
            ],
            "buses": [
                {
                    "bus_id": "bus_1",
                    "operator_id": "op_1",
                    "route_id": "r1",
                    "departure_minute": 0,
                    "battery_range_km": 150,
                }
            ],
            "weights": {"individual": 0.5, "operator": 0.3, "overall": 0.2},
        }
    )
