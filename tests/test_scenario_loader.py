from pathlib import Path

from bus_charging_scheduler.scenario_loader import list_scenarios, load_scenario
from bus_charging_scheduler.simulation import SimulationEngine


def test_load_assessment_scenario_from_json() -> None:
    scenario = load_scenario(Path("scenarios/scenario_1_even_spacing.json"))

    assert scenario.scenario_id == "scenario_1_even_spacing"
    assert scenario.average_speed_kmph == 60
    assert len(scenario.routes["bengaluru_kochi"].ordered_stops) == 6
    assert len(scenario.routes["kochi_bengaluru"].ordered_stops) == 6
    assert scenario.stations["A"].charger_count == 1
    assert len(scenario.buses) == 20
    assert scenario.buses[0].departure_minute == 19 * 60


def test_list_scenarios_discovers_json_files() -> None:
    names = {path.name for path in list_scenarios(Path("scenarios"))}

    assert names == {
        "scenario_1_even_spacing.json",
        "scenario_2_bunched_start.json",
        "scenario_3_asymmetric_load.json",
        "scenario_4_operator_heavy.json",
        "scenario_5_worst_case_convergence.json",
    }


def test_all_assessment_scenarios_run_without_rule_violations() -> None:
    for path in list_scenarios(Path("scenarios")):
        scenario = load_scenario(path)
        output = SimulationEngine(scenario).run()

        assert output.rule_violations == []
        assert output.summary_metrics["bus_count"] == len(scenario.buses)
        assert all(entry.battery_km >= 0 for entry in output.bus_timelines)
