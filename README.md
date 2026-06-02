# Bus Charging Scheduler

Config-driven electric bus charging scheduler for the May 2026 take-home assessment. It uses Python, Streamlit, `heapq` discrete event simulation, pluggable rules, weighted scoring, and pandas.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
python -m streamlit run app.py
```

Run tests:

```bash
pytest
```

## Architecture Overview

The app loads a JSON scenario, creates dataclass domain objects, and runs a discrete event simulation. Events are stored in a `heapq` priority queue and processed by timestamp.

Main event types:

- `BusDeparture`
- `BusArriveStation`
- `ChargingStart`
- `ChargingEnd`
- `BusArriveDestination`

The scheduler is not hardcoded to one direction. Each assessment scenario defines a Bengaluru-to-Kochi route and a Kochi-to-Bengaluru route that share the same A/B/C/D charging stations.

## Changing Weights

Weights live in each scenario JSON:

```json
"weights": {
  "individual": 1,
  "operator": 1,
  "overall": 1
}
```

The scoring formula is:

```text
score =
  w_individual * individual_metric +
  w_operator   * operator_metric +
  w_overall    * overall_metric
```

No Python code change is needed to tune these values.

## Adding Scenarios

Add a new `.json` file under `scenarios/`. The Streamlit dropdown discovers scenario files automatically. The repository ships the five assessment scenarios:

- Scenario 1 - Even spacing
- Scenario 2 - Bunched start
- Scenario 3 - Asymmetric load
- Scenario 4 - Operator-heavy
- Scenario 5 - Worst case convergence

Each scenario includes:

- `average_speed_kmph`
- `routes`
- `stations`
- `buses`
- `weights`
- `scheduler`

JSON schemas are in `schemas/` and document the expected shape.

## Adding Rules

Rules implement this interface:

```python
class Rule(Protocol):
    name: str
    def validate(self, context: RuleContext) -> RuleResult: ...
```

To add a `DriverShiftRule`, create a new class in `rules.py` and register it when creating `RuleEngine`:

```python
RuleEngine([RangeRule(), ChargerCapacityRule(), RouteOrderRule(), DriverShiftRule()])
```

The simulation engine calls rules through `RuleEngine`, so adding a rule does not require changing event processing.

## App Views

The Streamlit app provides:

- Scenario selector dropdown.
- Scenario data tables.
- Per-bus timeline.
- Per-station charging order.
