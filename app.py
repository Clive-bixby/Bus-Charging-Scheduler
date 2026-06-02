from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bus_charging_scheduler.scenario_loader import list_scenarios, load_scenario
from bus_charging_scheduler.simulation import SimulationEngine
from bus_charging_scheduler.ui_tables import (
    bus_timeline_table,
    buses_table,
    routes_table,
    station_order_table,
    stations_table,
    weights_table,
)


st.set_page_config(page_title="Bus Charging Scheduler", layout="wide")
st.title("Bus Charging Scheduler")

scenario_paths = list_scenarios(ROOT / "scenarios")
if not scenario_paths:
    st.error("No scenario files found in the scenarios directory.")
    st.stop()

labels = {load_scenario(path).name: path for path in scenario_paths}
selected = st.selectbox("Scenario", list(labels.keys()))
scenario = load_scenario(labels[selected])
output = SimulationEngine(scenario).run()

tab_input, tab_buses, tab_stations = st.tabs(
    ["Scenario Data", "Per-Bus Timeline", "Per-Station Charging Order"]
)

with tab_input:
    st.subheader(scenario.name)
    st.caption(f"Average speed: {scenario.average_speed_kmph:g} km/h")
    left, right = st.columns(2)
    with left:
        st.write("Routes")
        st.dataframe(routes_table(scenario), use_container_width=True, hide_index=True)
        st.write("Weights")
        st.dataframe(weights_table(scenario), use_container_width=True, hide_index=True)
    with right:
        st.write("Stations")
        st.dataframe(stations_table(scenario), use_container_width=True, hide_index=True)
        st.write("Buses")
        st.dataframe(buses_table(scenario), use_container_width=True, hide_index=True)

with tab_buses:
    timeline = bus_timeline_table(output)
    bus_ids = sorted(timeline["bus_id"].unique()) if not timeline.empty else []
    selected_buses = st.multiselect("Buses", bus_ids, default=bus_ids)
    if selected_buses:
        timeline = timeline[timeline["bus_id"].isin(selected_buses)]
    st.dataframe(timeline, use_container_width=True, hide_index=True)

with tab_stations:
    station_orders = station_order_table(output)
    station_ids = sorted(station_orders["station_id"].unique()) if not station_orders.empty else []
    selected_stations = st.multiselect("Stations", station_ids, default=station_ids)
    if selected_stations:
        station_orders = station_orders[station_orders["station_id"].isin(selected_stations)]
    st.dataframe(station_orders, use_container_width=True, hide_index=True)

if output.rule_violations:
    st.warning("Rule violations were detected.")
    st.json(output.rule_violations)
