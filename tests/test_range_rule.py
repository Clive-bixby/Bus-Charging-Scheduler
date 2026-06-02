from bus_charging_scheduler.models import Weights
from bus_charging_scheduler.rules import RangeRule, RuleContext
from bus_charging_scheduler.scenario_loader import parse_scenario
from bus_charging_scheduler.simulation import SimulationEngine


def test_range_rule_rejects_distance_beyond_battery() -> None:
    result = RangeRule().validate(
        RuleContext(
            scenario=_simple_scenario(),
            distance_km=241,
            battery_km=240,
        )
    )

    assert not result.valid


def test_simulation_never_records_negative_battery() -> None:
    output = SimulationEngine(_simple_scenario()).run()

    assert output.rule_violations == []
    assert all(entry.battery_km >= 0 for entry in output.bus_timelines)


def _simple_scenario():
    return parse_scenario(
        {
            "scenario_id": "range_test",
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
                    "initial_charge_km": 150,
                }
            ],
            "weights": Weights(0.5, 0.3, 0.2).__dict__,
        }
    )
