from bus_charging_scheduler.rules import RouteOrderRule, RuleContext
from bus_charging_scheduler.scenario_loader import parse_scenario


def test_route_order_rule_rejects_backtracking() -> None:
    scenario = parse_scenario(
        {
            "scenario_id": "route_order_test",
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

    result = RouteOrderRule().validate(
        RuleContext(
            scenario=scenario,
            route=scenario.routes["r1"],
            from_stop="A",
            to_stop="Start",
        )
    )

    assert not result.valid
