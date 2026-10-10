"""Predictive models: all six exist, compared with baselines, time-based, disclaimer present."""
import json

import pandas as pd

from src.config import TABLES


def test_forecast_targets_present_12_months():
    fc = pd.read_csv(TABLES / "forecast_next_12_months.csv")
    for t in ["revenue_total", "ros_collision", "billed_hours_collision", "tech_available_hours_collision", "cash_collections"]:
        assert (fc.target == t).sum() == 12, t
    assert any(t.startswith("parts_units_") for t in fc.target.unique())


def test_baselines_compared_and_holdout_present():
    ev = pd.read_csv(TABLES / "forecast_model_comparison.csv")
    assert {"Seasonal naive"} <= set(ev.method) and (ev.holdout == 1).any()
    ct = pd.read_csv(TABLES / "cycle_time_model_evaluation.csv")
    assert ct.model.str.startswith("Baseline").any() and len(ct) >= 3
    co = pd.read_csv(TABLES / "collections_model_evaluation.csv")
    assert co.method.str.contains("baseline", case=False).sum() >= 1


def test_disclaimer():
    r = json.loads((TABLES / "model_results.json").read_text())
    assert "does not establish real-world prediction accuracy" in r["disclaimer"]


def test_reorder_recommendations_and_completion_dates():
    assert len(pd.read_csv(TABLES / "reorder_point_recommendations.csv")) > 50
    e = pd.read_csv(TABLES / "estimated_completion_dates_open_ros.csv")
    assert len(e) > 0 and e.estimated_completion_date.notna().all()
