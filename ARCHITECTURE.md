# Architecture

## Why Discrete Event Simulation

Bus charging is a time-ordered resource contention problem. Buses depart, arrive, queue, charge, release chargers, and continue along the route. A discrete event simulation fits this naturally because the system only changes at event boundaries.

The engine uses `heapq` to process the next event by timestamp. This keeps the core loop small, deterministic, and easy to extend with new event types.

## Core Flow

1. Load scenario JSON into dataclasses.
2. Seed one `BusDeparture` event per bus.
3. Choose each bus charging plan from feasible route stops using scenario weights.
4. Process arrivals, charge requests, charge starts, charge ends, and destination arrivals.
5. Record per-bus timelines and per-station charging orders.
6. Render output tables in Streamlit.

## Modules

- `models.py`: dataclasses for routes, stations, buses, events, timelines, and output.
- `scenario_loader.py`: JSON parsing and lightweight validation.
- `simulation.py`: event queue, event handlers, runtime state, and transition logic.
- `scheduler.py`: feasible charging plan generation and waiting queue selection.
- `scoring.py`: configurable weighted scoring.
- `rules.py`: pluggable validation rules.
- `output.py`: summary metrics.
- `ui_tables.py`: pandas table shaping for Streamlit.

## Rules

The rule engine accepts pluggable rule objects:

```python
class Rule(Protocol):
    name: str
    def validate(self, context: RuleContext) -> RuleResult: ...
```

Initial rules:

- `RangeRule`: prevents travel beyond available battery.
- `ChargerCapacityRule`: prevents station capacity over-allocation.
- `RouteOrderRule`: prevents backtracking.

A future `DriverShiftRule` can be added by implementing the same interface and registering it with `RuleEngine`.

## Scoring

Queue decisions use:

```text
score =
  w_individual * individual_metric +
  w_operator   * operator_metric +
  w_overall    * overall_metric
```

Weights come from the scenario file. This lets reviewers test behavior changes without editing code.

## Scalability And Extensions

More stations:

- Add stops to `ordered_stops`.
- Add segments to the route.
- Add station objects for charging locations.

Multiple chargers:

- Change `charger_count` in the station config.
- The simulation creates charger IDs from config and keeps one active session per charger.

Different charging times:

- Change `default_charge_minutes` per station.

Different battery capacities:

- Change `battery_range_km` and `initial_charge_km` per bus.

Priority buses:

- Set `priority` on a bus.
- Extend `ScoringEngine.queue_score` if priority should dominate other metrics.

Multiple routes:

- Add more route objects.
- Point each bus at its `route_id`.
- The shipped assessment scenarios use two route objects, one per direction, and both share station IDs `A`, `B`, `C`, and `D`.

Electricity pricing:

- Use the existing `pricing` field on stations.
- Add a pricing-aware metric to `ScoringEngine`.

Driver shift constraints:

- Use `driver_shift` on buses.
- Add a `DriverShiftRule`.

Station outages:

- Use `outage_windows` on stations.
- Add an `OutageRule` to reject unavailable charging windows.

New operators:

- Add buses with new `operator_id` values.
- Operator fairness metrics are calculated dynamically from operator IDs.

## Assessment Assumptions

- The five provided scenario tables are encoded as JSON scenario files.
- Departure times are stored as clock strings such as `19:00` and parsed into minutes from midnight for simulation.
- Scenario 3 follows the assignment table and has 14 buses: 10 Bengaluru-to-Kochi and 4 Kochi-to-Bengaluru.
- All shipped scenarios use 60 km/h, 240 km range, 25 minute full charges, and one charger at each scheduling station.
- Bengaluru and Kochi are endpoints with slow chargers before departure, but they are not scheduling stations.

## Known Limits

The first scheduler is a greedy weighted heuristic. It is intentionally explainable and suitable for a take-home assessment. It does not globally optimize all bus schedules across the full network. If future requirements demand global optimality, the event model can stay intact while the plan selection component is replaced with a richer optimizer.
