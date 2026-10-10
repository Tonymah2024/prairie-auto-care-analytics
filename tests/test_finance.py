"""Integrated financial model: every validation check passes; statements tie; forecast stays integrated; capacity logic behaves."""
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from src.config import TABLES
from src.finance import forecast as F


def stmt(n):
    d = pd.read_csv(TABLES / f"fin_{n}.csv", index_col=0)
    return d.drop(columns=[c for c in ("label", "data_status") if c in d.columns])


def base():
    js = json.loads((TABLES / "fin_forecast_base.json").read_text())
    dv = pd.DataFrame(js["drivers"]).T
    dv.columns = range(1, F.H + 1)
    return {"A": js["A"], "drivers": dv, "opening": js["opening"]}


def test_all_financial_checks_pass():
    ch = pd.read_csv(TABLES / "fin_validation_checks.csv")
    assert len(ch) == 12 and (ch.result == "PASS").all(), ch[ch.result != "PASS"]


def test_balance_sheet_and_cash_tie_every_month():
    assert stmt("balance_sheet_monthly").loc["check"].abs().max() < 0.01
    assert stmt("cash_flow_monthly").loc["check"].abs().max() < 0.01


def test_wip_and_subledgers_reconcile():
    assert pd.read_csv(TABLES / "fin_wip_reconciliation.csv").difference.abs().max() < 0.01
    assert pd.read_csv(TABLES / "fin_subledger_reconciliation.csv").difference.abs().max() < 0.01


def test_branches_sum_to_consolidated_and_interbranch_eliminates():
    r = pd.read_csv(TABLES / "fin_branch_consolidation_reconciliation.csv")
    assert r.difference.max() < 0.01
    b = pd.read_csv(TABLES / "fin_branch_income_statement_monthly.csv")
    assert abs(b[b.line == "ib_rev"].direct.sum() + b[b.line == "ib_cost"].direct.sum()) < 0.01


def test_quarterly_and_annual_sum_months():
    m, q, y = stmt("income_statement_monthly"), stmt("income_statement_quarterly"), stmt("income_statement_annual")
    assert abs(m.loc["net_income"].sum() - q.loc["net_income"].sum()) < 0.01 and abs(m.loc["net_income"].sum() - y.loc["net_income"].sum()) < 0.01


def test_forecast_integrated_under_random_assumptions():
    b = base()
    rng = np.random.default_rng(3)
    for _ in range(25):
        sc = F.Scenario(eff_change=rng.uniform(-.3, .3), parts_cost_change=rng.uniform(-.2, .2), cycle_change=rng.uniform(-.4, .4), appt_change=rng.uniform(-.3, .3),
                        margin_change=rng.uniform(-.1, .1), collect_change=rng.uniform(-.5, .5), hires=float(rng.integers(0, 5)), expansion=rng.uniform(0, .6),
                        opex_change=rng.uniform(-.2, .2), rate_change=rng.uniform(-.02, .05))
        s = F.summary(F.run(sc, b))
        assert s["max_abs_bs_check"] < 0.01 and s["max_abs_cash_check"] < 0.01


def test_capacity_logic_efficiency_vs_volume():
    b = base()
    s0 = F.summary(F.run(F.SCENARIOS["Base"], b))
    eff = F.summary(F.run(replace(F.SCENARIOS["Base"], eff_change=.10), b))
    vol = F.summary(F.run(replace(F.SCENARIOS["Base"], appt_change=.10), b))
    assert eff["collision_overtime_hours"] <= s0["collision_overtime_hours"]           # efficiency cuts overtime
    assert (vol["net_revenue"] - s0["net_revenue"]) > 5 * abs(eff["net_revenue"] - s0["net_revenue"])   # demand, not efficiency, drives sales
    assert F.summary(F.run(replace(F.SCENARIOS["Base"], collect_change=-.2), b))["closing_cash"] > s0["closing_cash"]
    assert F.summary(F.run(replace(F.SCENARIOS["Base"], parts_cost_change=-.05), b))["gross_profit"] > s0["gross_profit"]


def test_excel_model_verified_when_excel_available():
    xl = json.loads((TABLES / "fin_excel_verification.json").read_text())
    assert xl.get("ok") in (True, None)
