"""Management recommendations, each quantified by re-running the integrated forecast engine against Base or by stated
arithmetic on the synthetic results. ILLUSTRATIVE ONLY - estimates for a fictional business, not guaranteed benefits."""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from src.config import END, TABLES
from src.finance import forecast as F


def _base():
    js = json.loads((TABLES / "fin_forecast_base.json").read_text())
    dv = pd.DataFrame(js["drivers"]).T
    dv.columns = range(1, F.H + 1)
    return {"A": js["A"], "drivers": dv, "opening": js["opening"]}


def delta(base, **kw):
    b0 = F.summary(F.run(F.SCENARIOS["Base"], base))
    r = F.summary(F.run(replace(F.SCENARIOS["Base"], **kw), base))
    return {"profit": r["operating_profit"] - b0["operating_profit"], "cash": r["closing_cash"] - b0["closing_cash"], "wc": r["closing_working_capital"] - b0["closing_working_capital"],
            "revenue": r["net_revenue"] - b0["net_revenue"]}


def build():
    base = _base()
    K = json.loads((TABLES / "findings.json").read_text())["metrics"]
    j = pd.read_csv(TABLES / "ro_job_costing.csv", parse_dates=["invoice_date"], low_memory=False)
    sup = pd.read_csv(TABLES / "supplier_performance.csv")
    po = pd.read_csv(TABLES / "purchase_orders_monthly.csv")
    rop = pd.read_csv(TABLES / "reorder_point_recommendations.csv")
    clm = pd.read_csv(TABLES / "claims_by_insurer.csv")
    ttm = j[(j.status == "Delivered") & (j.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365))]
    recs = []

    def add(**k):
        recs.append(k)

    d1 = delta(base, cycle_change=-0.15)
    worst = sup.sort_values("on_time_pct").head(2)
    add(area="Repair cycle time", title="Parts-first scheduling with daily supplier escalation for collision jobs",
        impact=d1["profit"], cash=d1["cash"],
        method=f"Parts waiting averages {K['collision_parts_wait']:.1f} days per collision job vs {K['collision_tech_wait']:.1f} days waiting for a technician. "
               f"Weakest on-time suppliers: {', '.join(f'{r.supplier_name} ({r.on_time_pct:.0f}%)' for r in worst.itertuples())}. Engine re-run with cycle time -15% "
               "(less work in progress, fewer waiting customers lost).",
        assumptions="Vehicles dropped off only when parts are confirmed; backorders escalated within 24 h; alternative certified parts approved faster.",
        kpis="Keys-to-keys days, parts waiting days, on-time vs original promise, CSAT", effort="Low", timeframe="0-3 months")
    d2 = delta(base, parts_cost_change=-0.03)
    add(area="Parts procurement", title="Preferred-supplier agreement and monthly price audit on the top OEM / aftermarket suppliers",
        impact=d2["profit"], cash=d2["cash"],
        method="Special-order parts are ~{:.0f}% of parts spend. Engine re-run with parts cost -3%.".format(K["special_order_share"]),
        assumptions="Volume rebate or discount of 3% on special-order parts; no change in quality or lead time.", kpis="Parts margin %, price variance vs estimate",
        effort="Medium", timeframe="3-6 months")
    em = po[po.po_type.str.startswith("Emergency")]
    em12 = em[em.month >= str(pd.Period(END, "M") - 11)].value.sum()
    prem = em12 * (0.12 / 1.12)
    a_r = rop[rop.recommended_reorder_point > rop.current_reorder_point.fillna(0)]
    add(area="Parts inventory", title="Seasonal, service-level reorder points for stocked parts (tires, oil, filters, brakes)",
        impact=prem * 0.6, cash=prem * 0.6,
        method=f"{K['emergency_orders_12m']:,} emergency (stockout) orders in 12 months, ${em12:,.0f} bought at a ~12% premium (${prem:,.0f}). "
               f"{len(a_r)} branch-SKUs need a higher seasonal reorder point. Assume 60% of the premium avoided.",
        assumptions="Reorder points from reorder_point_recommendations.csv (95/90/85% service by ABC class); weekly review kept.",
        kpis="Fill rate, emergency orders, inventory turnover, aged stock", effort="Low", timeframe="0-3 months")
    d4 = delta(base, collect_change=-0.20)
    nd = clm[clm.insurer_category.str.startswith("Non-DRP")]
    add(area="Insurance receivables", title="Same-day electronic invoicing with complete photo & supplement files; weekly follow-up of items past terms",
        impact=0.0, cash=d4["cash"],
        method=f"Insurer receivables ${K['insurer_outstanding']:,.0f} at 30-Sep-2026; average payment {K['insurer_payment_days']:.0f} days (non-DRP insurers slower: "
               f"{nd.avg_payment_days.mean():.0f} days). Engine re-run with collection delays -20%.",
        assumptions="Most delay is documentation and follow-up, not insurer policy; fictional insurers only.", kpis="Insurer DSO, receivables > 60 days, short-pays",
        effort="Low", timeframe="0-3 months")
    unp = ttm[(ttm.fully_loaded_profit < 0) & (ttm.payer_type != "Warranty (internal)")]
    top = unp.groupby("service_name").fully_loaded_profit.sum().sort_values().head(3)
    add(area="Job profitability", title="Price and quote review for jobs that do not cover shop overhead; teardown before fixed customer-pay quotes",
        impact=float(-unp.fully_loaded_profit.sum() * 0.4), cash=float(-unp.fully_loaded_profit.sum() * 0.36),
        method=f"{len(unp)} ROs ({len(unp) / max(len(ttm), 1):.0%}) fell ${-unp.fully_loaded_profit.sum():,.0f} short of direct cost + shop overhead "
               f"(${K['overhead_rate']:.0f} per clocked hour) in 12 months; largest gaps: {', '.join(f'{k} (${-v:,.0f})' for k, v in top.items())}. Assume 40% recovered "
               "through minimum charges, package pricing and quote discipline.",
        assumptions="Customers accept minimum labour charges / revised quotes; goodwill discounts approved by the branch manager only.",
        kpis="Fully loaded profit per RO, unprofitable RO count, estimate-to-actual labour variance", effort="Low", timeframe="0-3 months")
    add(area="Quality", title="Pre-delivery QC checklist and comeback root-cause review (lifetime warranty)",
        impact=K["rework_cost_ttm"] * 0.35, cash=K["rework_cost_ttm"] * 0.35,
        method=f"Warranty comebacks cost ${K['rework_cost_ttm']:,.0f} in parts & labour over 12 months ({K['comeback_rate_pct']:.1f}% of ROs). Assume 35% fewer comebacks.",
        assumptions="Comeback rates compared with the expected rate for each technician's job mix (no raw ranking).", kpis="Comeback rate, rework cost, CSAT",
        effort="Low", timeframe="0-6 months")
    d7 = delta(base, expansion=0.25)
    add(area="Growth", title="Grow detailing & paint protection at SE Concierge (insurer-referral and dealer packages)",
        impact=d7["profit"], cash=d7["cash"], method="Engine re-run with detailing & other services +25% (with installer labour).",
        assumptions="Demand exists at current prices; installer capacity added in line with volume.", kpis="SE revenue, SE contribution, PPF backlog days",
        effort="Medium", timeframe="3-9 months")
    d8 = delta(base, eff_change=0.10)
    add(area="Technician productivity", title="Flat-rate incentive and training to lift efficiency - paired with demand growth",
        impact=d8["profit"], cash=d8["cash"],
        method=f"Engine re-run with efficiency +10%: only ${d8['revenue']:,.0f} extra revenue because collision demand rarely exceeds capacity; the benefit is mainly "
               "lower overtime. Efficiency pays off when combined with volume growth.",
        assumptions="Demand-constrained most months; capacity binds only in winter peaks.", kpis="Efficiency, overtime %, productivity", effort="Medium", timeframe="3-6 months")
    df = pd.DataFrame(recs)
    df["value_score"] = (df.impact + df.cash.clip(lower=0) * 0.05) / df.effort.map({"Low": 1, "Medium": 2, "High": 3})
    df = df.sort_values("value_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    df = df.rename(columns={"impact": "operating_profit_impact_12m", "cash": "cash_impact_12m", "method": "methodology"})
    df["data_status"] = "SYNTHETIC - illustrative estimate for a fictional business"
    df.to_csv(TABLES / "recommendations.csv", index=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(build()[["rank", "area", "title", "operating_profit_impact_12m", "cash_impact_12m"]].round(0).to_string())
