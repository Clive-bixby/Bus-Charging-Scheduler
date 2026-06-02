from bus_charging_scheduler.scenario_loader import parse_scenario
from bus_charging_scheduler.simulation import SimulationEngine


def test_single_charger_serves_one_bus_at_a_time() -> None:
    output = SimulationEngine(_queue_scenario()).run()
    orders = [entry for entry in output.station_charging_orders if entry.station_id == "A"]

    assert len(orders) == 3
    for previous, current in zip(orders, orders[1:]):
        assert current.charge_start_minute >= previous.charge_end_minute
    assert [entry.wait_minutes for entry in orders] == [0.0, 25.0, 50.0]


def _queue_scenario():
    return parse_scenario(
        {
            "scenario_id": "queue_test",
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
                },
                {
                    "bus_id": "bus_2",
                    "operator_id": "op_1",
                    "route_id": "r1",
                    "departure_minute": 0,
                    "battery_range_km": 150,
                },
                {
                    "bus_id": "bus_3",
                    "operator_id": "op_1",
                    "route_id": "r1",
                    "departure_minute": 0,
                    "battery_range_km": 150,
                },
            ],
            "weights": {"individual": 1.0, "operator": 0.0, "overall": 0.0},
        }
    )
