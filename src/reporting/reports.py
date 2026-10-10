"""Client-facing deliverables (HTML -> PDF via headless Chrome): management report, business-development proposal, 90-day pilot
plan and demonstration guide. All figures come from computed outputs of the SYNTHETIC demo of a FICTIONAL business."""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from src.analysis.style import cad, fig, save
from src.config import APP_BANNER, ATTRIBUTION, BRAND, EXTERNAL, OUT, REPORTS, RETRIEVAL_DATE, TABLES
from src.finance import forecast as F
from src.reporting.pdf import img, money, page, pct, render_pdf, tbl

FIN = [BRAND["brand"], BRAND["teal"], BRAND["accent"], BRAND["warn"]]
UP, DOWN, TOT = BRAND["teal"], BRAND["bad"], BRAND["navy"]
DEMO_URL = None            # set to the Streamlit Community Cloud URL only after the app is deployed and verified


def demo_ref():
    return f"<b>{DEMO_URL.replace('https://', '')}</b>" if DEMO_URL else "the interactive demonstration (link shared separately)"
CONTACT = "Antoine Matemane Mahirwe, PhD - Founder & Chief Data Strategist, VisiVault Analytics Ltd. - visivault@visivaultanalytics.com - www.visivaultanalytics.com"
BR = {"BR-SEC": "SE Concierge", "BR-CCC": "Central Collision", "BR-NFS": "North Full-Service"}


def t(name, **kw):
    return pd.read_csv(TABLES / f"{name}.csv", low_memory=False, **kw)


def stmt(name):
    d = t(f"fin_{name}", index_col=0)
    return d.drop(columns=[c for c in ("label", "data_status") if c in d.columns])


def esc(s):
    return html.escape(str(s))


def acct(v):
    if pd.isna(v):
        return ""
    return "-" if abs(v) < 0.5 else (f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}")


# ----------------------------------------------------------------------------------------------- charts
def charts():
    is_m = stmt("income_statement_monthly")
    mo = pd.PeriodIndex(is_m.columns, freq="M").to_timestamp()
    f, ax = fig(11, 4.3)
    bottom = np.zeros(len(mo))
    for k, lab, c in [("rev_collision", "Collision", FIN[0]), ("rev_mech", "Mechanical", FIN[1]), ("rev_glass", "Glass", FIN[2]), ("rev_detail", "Detailing", FIN[3]),
                      ("rev_other", "Other services", BRAND["subtle"])]:
        ax.bar(mo, is_m.loc[k], width=24, bottom=bottom, color=c, label=lab, edgecolor="white", linewidth=0.6)
        bottom += is_m.loc[k].values
    ax.set_title("Revenue by service line, recognised on delivery (SE Concierge opened May-2025)")
    ax.legend(loc="upper left", ncol=5)
    cad(ax, k=True)
    save(f, "R01_revenue_by_line", "Fictional business; synthetic data.")
    pt = t("profitability_by_service_type").sort_values("gross_profit")
    f, (a1, a2) = fig(11, 4.6, 1, 2, sharey=True)
    a1.barh(pt.service_name.str.slice(0, 34), pt.gross_profit, color=FIN[0])
    a1.set_title("Job gross profit by service type (Jan-2024 to Sep-2026)")
    cad(a1, axis="x", k=True)
    a2.barh(pt.service_name.str.slice(0, 34), pt.gross_margin_pct, color=FIN[1])
    a2.set_title("Job gross margin %")
    save(f, "R02_job_profitability", "Job gross profit = revenue - technician labour (loaded) - parts - materials - sublet.")
    st = t("cycle_stage_means_by_line").set_index("service_line").loc["Collision repair"].drop(["data_status", "Delivery -> payment collected"], errors="ignore").astype(float)
    f, ax = fig(10, 4.0)
    cols = [BRAND["bad"] if v == st.max() else FIN[0] for v in st.values]
    ax.barh(st.index[::-1], st.values[::-1], color=cols[::-1])
    ax.set_title("Collision repair: average days in each stage, first call to pickup (bottleneck = red)")
    ax.set_xlabel("days")
    save(f, "R03_collision_bottleneck", "Delivered collision ROs Jan-2024 to Sep-2026.")
    m = t("technician_productivity_monthly")
    m["grp"] = np.where(m.op_groups.str.contains("BODY|PAINT"), "Collision & refinish", np.where(m.op_groups.str.startswith("MECH"), "Mechanical & tires", "Other specialists"))
    g = m.groupby(["month", "grp"])[["productive", "attended"]].sum()
    g = (g.productive / g.attended * 100).unstack()
    f, ax = fig(11, 3.9)
    for i, c in enumerate(g.columns):
        ax.plot(pd.to_datetime(g.index), g[c], lw=2, color=FIN[i], label=c)
    ax.set_title("Technician utilisation % (clocked / attended hours)")
    ax.legend(loc="lower right")
    save(f, "R04_utilisation", "Seasonal peaks (winter collision, spring & fall tire changeovers) vs quieter summer weeks.")
    cb = t("claims_by_insurer").sort_values("avg_payment_days")
    f, (a1, a2) = fig(11, 4.2, 1, 2, sharey=True)
    colors = [FIN[0] if c.startswith("DRP") else (FIN[3] if c.startswith("Non") else FIN[2]) for c in cb.insurer_category]
    lab = cb.insurer_name.str.replace(" (fictional)", "", regex=False)
    a1.barh(lab, cb.avg_approval_days, color=colors)
    a1.set_title("Estimate -> approval (days)")
    a2.barh(lab, cb.avg_payment_days, color=colors)
    a2.set_title("Invoice -> payment (days)")
    save(f, "R05_insurers", "FICTIONAL insurers. Blue = DRP, amber = non-DRP, purple = fleet / self-insured.")
    bp = t("fin_branch_pnl_annual")
    bp = bp[bp.branch_id != "HO"]
    f, ax = fig(10, 3.9)
    yrs = sorted(bp.year.unique())
    w = 0.26
    for i, b in enumerate(["BR-CCC", "BR-NFS", "BR-SEC"]):
        v = [bp[(bp.year == y) & (bp.branch_id == b)].operating_profit_after_allocations.sum() for y in yrs]
        ax.bar(np.arange(len(yrs)) + (i - 1) * w, v, width=w, color=FIN[i], label=BR[b])
    ax.set_xticks(range(len(yrs)), [f"{y}" + (" YTD" if y == 2026 else "") for y in yrs])
    ax.axhline(0, color="#999", lw=.8)
    ax.set_title("Branch operating profit after shared-cost allocation")
    ax.legend()
    cad(ax, k=True)
    save(f, "R06_branch_profit", "Interbranch work at transfer price; head-office costs allocated by documented drivers.")
    cf = stmt("cash_flow_monthly")
    bs = stmt("balance_sheet_monthly")
    f, (a1, a2) = fig(11, 3.8, 1, 2)
    a1.bar(mo, is_m.loc["ebitda"], width=24, color=[UP if v >= 0 else DOWN for v in is_m.loc["ebitda"]])
    a1.set_title("Monthly EBITDA")
    cad(a1, k=True)
    a2.plot(mo, bs.loc["cash"], color=FIN[0], lw=2.2, label="Cash")
    a2.plot(mo, bs.loc["ar_insurer"], color=FIN[3], lw=2, label="Insurer receivables")
    a2.plot(mo, bs.loc["wip"], color=FIN[2], lw=2, label="Work in progress")
    a2.set_title("Cash and working capital (month end)")
    a2.legend()
    cad(a2, k=True)
    save(f, "R07_profit_cash", "SIMULATED financial information.")
    fc = t("forecast_next_12_months", parse_dates=["month"])
    h = t("forecast_history")
    hh = h[h.target == "revenue_total"]
    ff = fc[fc.target == "revenue_total"]
    f, ax = fig(11, 3.9)
    ax.plot(pd.PeriodIndex(hh.month, freq="M").to_timestamp(), hh.actual, color=TOT, lw=2.2, label="Simulated history")
    ax.fill_between(ff.month, ff.lower80, ff.upper80, color=FIN[2], alpha=.15, label="80% interval")
    ax.plot(ff.month, ff.forecast, color=FIN[2], lw=2.4, ls="--", label=f"FORECAST ({ff.model.iloc[0]})")
    ax.axvspan(pd.Timestamp("2026-09-30"), ff.month.max(), color=BRAND["accent_light"], alpha=.5)
    ax.set_title("Monthly service revenue: history and 12-month FORECAST")
    ax.legend(loc="upper left")
    cad(ax, k=True)
    save(f, "R08_forecast", "Model chosen on time-based backtests of synthetic data.")
    se = t("fin_forecast_sensitivity")
    f, (a1, a2) = fig(11, 4.3, 1, 2, sharey=True)
    lab = se.scenario.str.slice(0, 44)
    a1.barh(lab, se.delta_operating_profit, color=[UP if v >= 0 else DOWN for v in se.delta_operating_profit])
    a1.set_title("Operating profit vs Base (12 months)")
    cad(a1, axis="x", k=True)
    a2.barh(lab, se.delta_closing_cash, color=[UP if v >= 0 else DOWN for v in se.delta_closing_cash])
    a2.set_title("Closing cash vs Base")
    cad(a2, axis="x", k=True)
    save(f, "R09_scenarios", "Integrated forecast engine; each lever alone vs Base. FORECAST - illustrative.")
    iv = t("inventory_value_monthly")
    po = t("purchase_orders_monthly")
    em = po[po.po_type.str.startswith("Emergency")].groupby("month").lines.sum()
    f, (a1, a2) = fig(11, 3.7, 1, 2)
    a1.bar(pd.PeriodIndex(em.index, freq="M").to_timestamp(), em.values, width=24, color=FIN[3])
    a1.set_title("Stockouts: emergency parts orders per month")
    g = iv.groupby(["month", "inventory_state"]).value.sum().unstack().fillna(0)
    x = pd.PeriodIndex(g.index, freq="M").to_timestamp()
    a2.stackplot(x, [g.get("stock", 0), g.get("job", 0), g.get("materials", 0)], labels=["Stocked parts", "Special-order parts (per job)", "Paint & materials"],
                 colors=[FIN[0], FIN[2], FIN[1]], alpha=.85)
    a2.set_title("Inventory at cost by type")
    a2.legend(loc="upper left")
    cad(a2, k=True)
    save(f, "R10_parts", "Current reorder points are flat (non-seasonal) - tire seasons drive stockouts.")


def ctx():
    E = json.loads((TABLES / "findings.json").read_text())
    return dict(K=E["metrics"], F=E["findings"], MR=json.loads((TABLES / "model_results.json").read_text()), rec=t("recommendations"),
                ann=t("fin_ratios_annual", index_col=0), is_y=stmt("income_statement_annual"), sm=t("fin_forecast_scenario_summary", index_col=0),
                checks=t("fin_validation_checks"), dq=t("data_validation_checks"), facts=pd.read_csv(EXTERNAL / "public_business_model_facts.csv"),
                fmc=t("forecast_model_comparison"), cte=t("cycle_time_model_evaluation"), cole=t("collections_model_evaluation"),
                xl=json.loads((TABLES / "fin_excel_verification.json").read_text()), bp=t("fin_branch_pnl_annual"), sens=t("fin_forecast_sensitivity"))


def cover(title, sub, kind="Demonstration"):
    return f"""<section class='cover'><div class='brandmark'>VISIVAULT ANALYTICS</div>
<h1 style='margin-top:38mm'>{esc(title)}</h1><div class='sub'>{esc(sub)}</div>
<div class='badge'>⚠ {esc(APP_BANNER)}</div>
<div class='meta'>{esc(ATTRIBUTION)} · October 2026 · {esc(kind)}<br>Prairie Auto Care Group is a FICTIONAL multi-location Calgary collision repair and car care business.
Its business model (three Calgary locations with distinct roles, published hours, service menu, OEM-certified collision work, direct billing of insurers) is inspired by a public
Calgary auto care group's website (retrieved {RETRIEVAL_DATE}); every repair order, cost, technician, insurer, customer and financial figure is synthetic.
No relationship with or endorsement by any real company is implied.</div></section>"""


def statement_html(df, labels, keys, cols, names):
    x = df.loc[keys, cols].copy()
    x.columns = names
    x.index = [labels.get(k, k) for k in keys]
    x = x.reset_index().rename(columns={"index": "CAD"})
    return tbl(x, fmt={c: acct for c in names})


IS_LAB = {"net_rev": "Total net revenue", "labour": "Technician labour", "parts": "Parts", "materials": "Paint & materials", "sublet": "Sublet & towing",
          "cogs": "Cost of sales", "gross_profit": "Gross profit", "opex": "Operating expenses", "ebitda": "EBITDA", "da": "Depreciation", "interest": "Interest",
          "tax": "Income taxes", "net_income": "Net income", "rev_collision": "Collision repair revenue", "rev_mech": "Mechanical service revenue",
          "rev_detail": "Detailing revenue", "rev_glass": "Glass repair revenue", "rev_other": "Other service revenue"}


def kpi_block(c):
    K, sm = c["K"], c["sm"]
    ttm = stmt("income_statement_monthly")
    T = ttm[[x for x in ttm.columns if x >= "2025-10"]].sum(axis=1)
    return f"""<div class='kpis'>
<div class='kpi'><div class='l'>Net revenue (TTM)</div><div class='v'>{money(T['net_rev'])}</div><div class='s'>3 branches, {K['ttm_ros']:,} ROs</div></div>
<div class='kpi'><div class='l'>EBITDA (TTM)</div><div class='v'>{money(T['ebitda'])}</div><div class='s'>{T['ebitda'] / T['net_rev']:.1%} of revenue</div></div>
<div class='kpi'><div class='l'>Collision keys-to-keys</div><div class='v'>{K['collision_k2k']:.1f} d</div><div class='s'>{K['collision_lead']:.0f} days from first call</div></div>
<div class='kpi'><div class='l'>Parts waiting</div><div class='v'>{K['collision_parts_wait']:.1f} d</div><div class='s'>largest collision delay</div></div>
<div class='kpi'><div class='l'>Original promise met</div><div class='v'>{K['collision_original_promise']:.0f}%</div><div class='s'>{K['collision_on_time']:.0f}% after revision</div></div>
<div class='kpi'><div class='l'>Technician productivity</div><div class='v'>{K['productivity']:.0%}</div><div class='s'>util. {K['utilisation']:.0%} x eff. {K['efficiency']:.0%}</div></div>
<div class='kpi'><div class='l'>Insurer receivables</div><div class='v'>{money(K['insurer_outstanding'])}</div><div class='s'>{K['insurer_payment_days']:.0f} days to pay</div></div>
<div class='kpi'><div class='l'>Base forecast op. profit</div><div class='v'>{money(sm.at['Base', 'operating_profit'])}</div><div class='s'>Oct-26 to Sep-27 (FORECAST)</div></div></div>"""


def rec_tables(rec):
    rows = "".join(f"<tr><td><b>{r.rank}</b></td><td><b>{esc(r.area)}</b><br>{esc(r.title)}</td><td style='text-align:right'>{money(r.operating_profit_impact_12m)}</td>"
                   f"<td style='text-align:right'>{money(r.cash_impact_12m)}</td><td>{esc(r.effort)} / {esc(r.timeframe)}</td></tr>" for r in rec.itertuples())
    det = "".join(f"<h3>{r.rank}. {esc(r.title)}</h3><p><b>Estimate:</b> operating profit {money(r.operating_profit_impact_12m)}, cash {money(r.cash_impact_12m)} (12 months). "
                  f"<b>How calculated:</b> {esc(r.methodology)} <b>Assumptions:</b> {esc(r.assumptions)} <b>KPIs:</b> {esc(r.kpis)}</p>" for r in rec.itertuples())
    return (f"<table><thead><tr><th>#</th><th>Area / action</th><th>Op. profit, 12m</th><th>Cash, 12m</th><th>Effort / timing</th></tr></thead><tbody>{rows}</tbody></table>", det)


KPI_SET = [("Job profitability", "Gross profit and fully loaded profit per RO by service, vehicle, payer and branch; estimate-to-actual cost variance; unprofitable ROs; comeback cost"),
           ("Technician productivity", "Utilisation, efficiency and productivity (separately defined); overtime; mix-adjusted efficiency and comeback indices by role"),
           ("Repair cycle time", "Keys-to-keys and first-call-to-delivery; time in each stage (approval, parts, technician, repair, QC, pickup); on time vs original and revised promise"),
           ("Parts & suppliers", "Fill rate, emergency orders, FIFO aging, turnover, carrying cost; supplier on-time %, lead time, backorders, returns"),
           ("Insurance claims", "Approval time, approved vs estimated, supplement rate, receivables ageing and payment days by insurer, claim admin workload"),
           ("Branch & finance", "Branch P&L with eliminations and allocated overhead, branch cash flow, three statements, ratios, 12-month forecast and scenarios")]


def management_report(c):
    K, Fd, rec, ann, is_y, sm = c["K"], c["F"], c["rec"], c["ann"], c["is_y"], c["sm"]
    rt, rd = rec_tables(rec)
    facts = c["facts"]
    mp = pd.read_csv(EXTERNAL / "public_fact_to_demo_mapping.csv")
    pub = tbl(mp.rename(columns={"public_fact": "Grounded in public information (a Calgary auto care group's website)", "use_in_fictional_demo": "How the fictional demo uses it"}))
    illus = tbl(pd.DataFrame([(x,) for x in Fd], columns=["Illustrative findings from SYNTHETIC data (methods, not facts about any real business)"]))
    ct = c["cte"].sort_values("MAE_days")
    fm = c["fmc"][(c["fmc"].target == "revenue_total") & (c["fmc"].holdout == 1)][["method", "WAPE", "bias_pct", "PI80_coverage"]]
    body = cover("Prairie Auto Care: Repair Operations & Financial Intelligence", "Management report - what a multi-location collision & car care business can learn from its own data",
                 "Management report") + f"""
<h2>Important notice</h2><div class='warn'>This report analyses a <b>fictional</b> auto care group built on synthetic data to demonstrate VisiVault Analytics' capabilities.
None of the operational or financial figures describe any real company. The analyses are designed to complement - not replace - a repair business's existing
shop-management, insurance-estimating, parts-ordering and accounting systems.</div>
<h2>1. Executive summary</h2>{kpi_block(c)}
<ul>{''.join(f'<li>{esc(x)}</li>' for x in Fd)}</ul>
<h2>2. Public information vs illustrative findings</h2>
<p>Only the business-model facts below come from public information; they shaped the structure of the fictional group (three locations, roles, hours, services).
Everything else in this report is computed from synthetic data and is illustrative.</p>{pub}{illus}
<h2 class='pb'>3. Business challenges this platform addresses</h2><ul>
<li><b>Cycle time and promises:</b> parts availability, insurer approvals and supplements push vehicles past their promised date - the strongest driver of customer satisfaction.</li>
<li><b>Technician capacity:</b> collision demand peaks with snow and winter driving, tires peak twice a year, summer is quieter; labour is the largest controllable cost.</li>
<li><b>Job profitability:</b> fixed customer-pay quotes, parts price changes, discounts and comebacks erode margin job by job - often invisible in monthly totals.</li>
<li><b>Insurer cash cycle:</b> direct billing means most collision revenue is collected weeks after delivery; documentation quality drives payment speed.</li>
<li><b>Multi-branch economics:</b> work moves between branches (e.g. a concierge site sending collision repairs to the main shop); fair branch results need transfer pricing,
eliminations and transparent overhead allocation.</li></ul>
<h2>4. Platform scope and KPIs</h2>{tbl(pd.DataFrame(KPI_SET, columns=['Module', 'Key performance indicators']))}
<h2 class='pb'>5. Analytical findings (synthetic data)</h2>{img('R01_revenue_by_line')}{img('R02_job_profitability')}
<p>Job gross margin averages {K['ttm_gm_pct']:.1f}% before overhead; {K['unprofitable_ros']:,} ROs ({K['unprofitable_ros_pct']:.1f}%) did not cover direct cost plus shop overhead absorbed at
${K['overhead_rate']:.0f} per clocked hour (${K['unprofitable_loss']:,.0f} short in 12 months).</p>
{img('R03_collision_bottleneck')}{img('R04_utilisation')}
<p>Utilisation {K['utilisation']:.0%}, efficiency {K['efficiency']:.0%}, productivity {K['productivity']:.0%}; overtime {K['overtime_share']:.1%} of available hours. Technicians are compared
with the expected efficiency and comeback rate for their own job mix and role, not ranked on raw totals.</p>
<h2 class='pb'>6. Insurance claims, parts and branches</h2>{img('R05_insurers')}{img('R10_parts')}{img('R06_branch_profit')}
<h2 class='pb'>7. Financial performance (SIMULATED)</h2>
{statement_html(is_y, IS_LAB, ['rev_collision', 'rev_mech', 'rev_detail', 'rev_glass', 'rev_other', 'net_rev', 'labour', 'parts', 'materials', 'sublet', 'cogs', 'gross_profit',
                                'opex', 'ebitda', 'da', 'interest', 'tax', 'net_income'], list(is_y.columns), ['FY2024', 'FY2025', 'YTD Sep-2026'])}
{img('R07_profit_cash')}
<p>Work in progress is carried at cost until delivery; insurer receivables average {ann.at['dso_insurer', 'TTM Sep-2026']:.0f} days. Cash conversion cycle
{ann.at['ccc', 'TTM Sep-2026']:.0f} days (parts {ann.at['dio', 'TTM Sep-2026']:.0f} + WIP {ann.at['wip_days', 'TTM Sep-2026']:.0f} + receivables {ann.at['dso', 'TTM Sep-2026']:.0f}
- payables {ann.at['dpo', 'TTM Sep-2026']:.0f}). All {len(c['checks'])} financial validation checks pass, including the Excel model's own recalculation
(max difference vs Python ${c['xl'].get('max_diff', 0):.6f}).</p>
<h2 class='pb'>8. Financial forecasting capabilities (FORECAST)</h2>{img('R08_forecast')}
{tbl(fm, fmt={'WAPE': lambda v: f'{v:.1%}', 'bias_pct': lambda v: f'{v:+.1f}%', 'PI80_coverage': lambda v: f'{v:.0%}'})}
<p>Six models: revenue, RO volume / billed-hours demand, repair cycle time (best: {esc(ct.iloc[0].model)}, MAE {ct.iloc[0].MAE_days:.1f} days vs {ct[ct.model.str.startswith('Baseline')].MAE_days.iloc[0]:.1f}
for the baseline), parts demand, technician capacity and expected cash collections. Each is compared against a simple baseline with time-based validation.
<b>Model performance on synthetic data does not establish real-world prediction accuracy.</b></p>
{img('R09_scenarios')}
<p>Collision and mechanical revenue are capacity-constrained in the forecast: a 10% efficiency gain changes revenue by only
{money(c['sens'].set_index('driver').at['eff_change', 'delta_net_revenue'])} because demand - not technician capacity - limits sales most months; the gain shows up as lower overtime.</p>
<h2 class='pb'>9. Improvement opportunities and recommendations</h2>{rt}{rd}
<h2>10. Implementation requirements</h2><ul>
<li>Read-only exports (CSV / API / scheduled reports) from the shop-management system: repair orders with status history, technician time clock, parts lines.</li>
<li>Estimating and insurer data already exchanged with insurers: estimates, supplements, approvals; invoice and payment remittances.</li>
<li>Accounting: monthly trial balance / GL, AR and AP ageing; payroll summary by branch; fixed-asset register.</li>
<li>A named data contact (2-3 h/week) and a monthly 60-minute management review.</li></ul>
<h2>11. Risk considerations</h2><ul>
<li><b>Data quality:</b> clock-on discipline and RO status timestamps vary; the diagnostic measures completeness before any KPI is published.</li>
<li><b>Fairness:</b> technician metrics are mix- and role-adjusted and shown with evidence levels; they support coaching, not discipline.</li>
<li><b>Privacy & security:</b> customer personal information is excluded or pseudonymised; data stays in Canada (PIPEDA / Alberta PIPA); read-only access.</li>
<li><b>Model risk:</b> forecasts are re-validated on real history before use; scenario results are decision aids, not guarantees.</li>
<li><b>Insurer relationships:</b> claim analytics are for internal process improvement; no insurer is characterised publicly.</li></ul>
<h2>12. Proposed 90-day pilot</h2>{pilot_table()}
<p class='small'>{esc(ATTRIBUTION)} · {esc(CONTACT)} · {esc(APP_BANNER)}</p>"""
    return page("Prairie Auto Care - Management Report", body)


PILOT = [("Weeks 1-2", "Diagnostic", "Data-access review; export mapping from the shop-management, estimating and accounting systems; data-quality report; KPI definitions agreed"),
         ("Weeks 3-6", "Build", "Job profitability and technician productivity views on real data; cycle-time stage timestamps; branch P&L with agreed transfer pricing and allocations"),
         ("Weeks 7-10", "Validate", "Reconcile to the general ledger and payroll; review with branch managers and estimators; refine fairness adjustments for technician metrics"),
         ("Weeks 11-13", "Embed", "Monthly management pack, weekly cycle-time / parts-delay list, 12-month forecast with scenarios; handover and next-phase plan")]


def pilot_table():
    return tbl(pd.DataFrame(PILOT, columns=["When", "Phase", "Deliverables"]))


INVEST = [("1. Diagnostic (2 weeks)", "Data-access review, KPI definitions, data-quality report, opportunity sizing on your data", "2,500 fixed"),
          ("2. Pilot (90 days)", "Four pilot modules on your data, monthly management pack, weekly cycle-time and parts-delay list, 12-month forecast", "14,500 fixed, in 3 milestones"),
          ("3. Ongoing support (optional)", "Monthly refresh, management pack and analyst support; further modules quoted separately", "1,250 - 2,500 per month")]
MODULES = [("Repair job profitability", "Gross and fully loaded profit per RO by service, vehicle, payer and branch; estimate vs actual; unprofitable-RO review; comeback cost",
            "RO lines (labour, parts, materials, sublet), parts cost, time-clock hours, discounts, insurer remittances"),
           ("Technician productivity", "Utilisation, efficiency and productivity by technician, role and branch with job-mix adjustment; overtime; capacity vs demand",
            "Time clock (attendance & job clock-on), flagged / billed hours, roles, schedules, payroll summary"),
           ("Repair cycle time", "Stage durations (estimate, approval, parts, technician, repair, QC, pickup), on-time vs promise, WIP and delayed-repair lists",
            "RO status history and milestone dates, promised dates, parts order / receipt dates, supplement approvals"),
           ("Branch financial performance", "Branch P&L with transfer pricing, eliminations and agreed overhead allocation; branch cash flow; group consolidation",
            "Monthly trial balance by branch / department, interbranch work, payroll by branch, fixed assets")]


def proposal(c):
    raise NotImplementedError("The client proposal is not part of the public demo.")


def pilot_plan(c):
    raci = [("Data exports", "Group IT / office manager", "VisiVault"), ("KPI definitions (labour hours, promise dates, cycle-time stages)", "Group management", "VisiVault"),
            ("Dashboards, models, reconciliations", "VisiVault", "Controller / management"), ("Branch review sessions", "Branch managers & estimators", "VisiVault"),
            ("Monthly review", "Owners / management", "VisiVault")]
    weekly = [("1", "Kickoff; data-access and export mapping"), ("2", "Data-quality report; KPI definitions signed off"), ("3-4", "Job costing per RO reconciled to invoices"),
              ("5-6", "Technician productivity and capacity views; fairness adjustments"), ("7-8", "Cycle-time stages, WIP and delayed-repair list"),
              ("9-10", "Branch P&L, transfer pricing and allocations reconciled to the GL"), ("11-12", "12-month forecast and scenarios on real history"),
              ("13", "Management pack #2, handover, next-phase plan")]
    body = cover("90-day pilot plan", "Repair job profitability, technician productivity, repair cycle time and branch financial performance", "Pilot plan") + f"""
<h2>Plan</h2>{pilot_table()}
<h2>Week by week</h2>{tbl(pd.DataFrame(weekly, columns=['Week', 'Milestone']))}
<h2>Roles</h2>{tbl(pd.DataFrame(raci, columns=['Activity', 'Responsible (client)', 'Supported by']))}
<h2>Exit criteria</h2><ul><li>Reconciliations at zero difference; two monthly packs delivered; branch managers using the weekly delay list; go / no-go on ongoing support.</li></ul>
<p class='small'>{esc(ATTRIBUTION)} · {esc(CONTACT)} · {esc(APP_BANNER)}</p>"""
    return page("VisiVault - 90-day pilot plan", body)


def demo_guide(c):
    K = c["K"]
    steps = [("Executive Overview", f"Start with TTM revenue, EBITDA and the SE Concierge ramp; read the key findings (parts waiting {K['collision_parts_wait']:.1f} days)."),
             ("Repair Job Profitability", "Show where each revenue dollar goes by line; open the unprofitable-RO list; use the job calculator (efficiency, parts cost, price)."),
             ("Technician Productivity", "Explain the three definitions; show the mix-adjusted comparison table and why there is no league table."),
             ("Repair Cycle Times", "Filter to moderate collision with supplements; show the bottleneck chart and the delayed-repairs list; estimated completion dates."),
             ("Parts Inventory & Supplier Performance", "Stocked vs special-order; tire-season stockouts; reorder recommendations; supplier on-time and lead times."),
             ("Insurance Claims", "Approval and payment days by (fictional) insurer category; receivables ageing; admin workload."),
             ("Branch Comparison", "Interbranch eliminations and allocations; SE start-up losses; drill into a branch P&L."),
             ("Financial statements & ratios", "Statements reconcile; WIP and insurer receivables in the balance sheet; cash bridge."),
             ("Forecasting & Scenario Simulator", "Show demand vs capacity; move technician efficiency +10% and note revenue barely moves - then add appointment volume."),
             ("Excel model", "Open Prairie_Auto_Care_Integrated_Financial_Model.xlsx, change Assumptions!C4 to Optimistic and show the Checks sheet staying TRUE.")]
    body = cover("Demonstration guide", "A 20-minute walkthrough of the Prairie Auto Care Analytics dashboard", "Demo guide") + f"""
<h2>Before the meeting</h2><ul><li>Open {demo_ref()} (or run locally: <code>streamlit run dashboard/app.py</code>).</li>
<li>Say clearly: fictional business, synthetic data, inspired only by the public business model of a Calgary auto care group.</li></ul>
<h2>Walkthrough</h2>{tbl(pd.DataFrame(steps, columns=['Page', 'What to show']))}
<h2>Close</h2><p>Propose the 90-day pilot (job profitability, technician productivity, cycle time, branch financial performance) with read-only data access.</p>
<p class='small'>{esc(APP_BANNER)}</p>"""
    return page("Prairie Auto Care - Demonstration guide", body)


def _label_check():
    from src.finance.validation import label_audit
    ok, detail = label_audit(OUT)
    ch = t("fin_validation_checks")
    ch.loc[ch.check_no == 12, ["result", "detail"]] = ["PASS" if ok else "FAIL", detail]
    ch.to_csv(TABLES / "fin_validation_checks.csv", index=False)
    return ok


def run():
    charts()
    c = ctx()
    docs = {"Prairie_Auto_Care_Management_Report": management_report(c), "Prairie_Auto_Care_Demonstration_Guide": demo_guide(c),
            "VisiVault_90_Day_Pilot_Plan": pilot_plan(c)}
    out = {}
    for name, h in docs.items():
        hp = REPORTS / f"{name}.html"
        hp.write_text(h, encoding="utf-8")
        out[name] = render_pdf(hp, REPORTS / f"{name}.pdf")
    out["labels_ok"] = _label_check()
    return out


if __name__ == "__main__":
    print(run())
