from bus_charging_scheduler.scheduler import GreedyWeightedScheduler
from bus_charging_scheduler.scenario_loader import parse_scenario
from bus_charging_scheduler.scoring import ScoringEngine
from bus_charging_scheduler.simulation import SimulationEngine


def test_operator_weight_changes_waiting_queue_choice() -> None:
    scenario = _two_bus_scenario({"individual": 0.0, "operator": 1.0, "overall": 0.0})
    engine = SimulationEngine(scenario)
    scheduler = GreedyWeightedScheduler(scenario, ScoringEngine(scenario.weights))
    state = engine.state
    state.operator_charge_counts = {"op_a": 3, "op_b": 0}

    scheduler.enqueue_waiting_bus("A", "bus_a", waiting_since=10, sequence=1, state=state)
    scheduler.enqueue_waiting_bus("A", "bus_b", waiting_since=20, sequence=2, state=state)

    chosen = scheduler.pop_next_waiting_bus("A", current_time=30, state=state)

    assert chosen is not None
    assert chosen.bus_id == "bus_b"


def test_individual_weight_changes_waiting_queue_choice() -> None:
    scenario = _two_bus_scenario({"individual": 1.0, "operator": 0.0, "overall": 0.0})
    engine = SimulationEngine(scenario)
    scheduler = GreedyWeightedScheduler(scenario, ScoringEngine(scenario.weights))
    state = engine.state
    state.operator_charge_counts = {"op_a": 3, "op_b": 0}

    scheduler.enqueue_waiting_bus("A", "bus_a", waiting_since=10, sequence=1, state=state)
    scheduler.enqueue_waiting_bus("A", "bus_b", waiting_since=20, sequence=2, state=state)

    chosen = scheduler.pop_next_waiting_bus("A", current_time=30, state=state)

    assert chosen is not None
    assert chosen.bus_id == "bus_a"


def _two_bus_scenario(weights):
    return parse_scenario(
        {
            "scenario_id": "weights_test",
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
                    "bus_id": "bus_a",
                    "operator_id": "op_a",
                    "route_id": "r1",
                    "departure_minute": 0,
                    "battery_range_km": 150,
                },
                {
                    "bus_id": "bus_b",
                    "operator_id": "op_b",
                    "route_id": "r1",
                    "departure_minute": 0,
                    "battery_range_km": 150,
                },
            ],
            "weights": weights,
        }
    )
