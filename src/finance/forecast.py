"""Integrated, driver-based 12-month financial forecast (Oct-2026 to Sep-2027) and scenario engine (SIMULATED).

Single source of truth: each line is ONE formula template (ROWS) evaluated in Python AND written into the Excel model as a
live formula. Tokens: {key} this month | {key[-k]} k months earlier (t=0 = actual 30-Sep-2026 opening; before = 0) |
{key[+k]} k months later | {$name} active scenario assumption.

Auto-repair mechanics (explicit drivers, no growth plugs):
  * Collision and mechanical revenue are CAPACITY-CONSTRAINED: billed hours delivered = MIN(demand + carried backlog,
    regular technician capacity x efficiency + limited overtime). Demand comes from the RO-volume / billed-hours forecasts;
    capacity from the technician-capacity forecast. Unmet demand waits (part of it is lost each month).
    => a technician-efficiency gain only adds sales when demand exceeds capacity; otherwise it shows up as lower overtime.
  * Detailing, glass and other services are demand-driven (revenue forecasts x appointment-volume change).
  * Technician payroll is a staffing plan (regular hours), plus overtime from the capacity model, plus any new hires.
  * Working capital: insurer receivables = insurer days x insurer-billed revenue; WIP = WIP days x cost of sales (falls with cycle
    time); parts & materials inventory = months of cover; supplier & vendor payables, accrued payroll, GST and tax timing.
  * Loans follow their amortisation schedules; revolver cash-band rule; year-end dividend at 40% of net income.
All values are SIMULATED.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.config import END, TABLES
from src.finance import policy as P
from src.finance.ledger import fixed_asset_schedule, loan_schedule, prime_rate
from src.finance.statements import MONTHS

H = 12
FC_MONTHS = pd.period_range("2026-10", periods=H, freq="M")
TTM = pd.period_range("2025-10", END, freq="M")


@dataclass
class Scenario:
    eff_change: float = 0.0             # technician labour efficiency (billed / clocked hours), +0.10 = +10%
    parts_cost_change: float = 0.0      # parts procurement cost, -0.05 = 5% cheaper
    cycle_change: float = 0.0           # average repair cycle time, -0.15 = 15% shorter (less WIP, fewer customers lost while waiting)
    appt_change: float = 0.0            # appointment / RO volume, +0.10 = +10% demand
    margin_change: float = 0.0          # gross-margin improvement, relative (+0.05 = gross profit +5% before scenario)
    collect_change: float = 0.0         # receivable collection delays, -0.20 = insurer & fleet days 20% shorter
    hires: float = 0.0                  # additional collision technicians from Dec-2026
    expansion: float = 0.0              # expansion of detailing & paint protection / other services, +0.25 = +25% volume
    opex_change: float = 0.0            # controllable operating expenses
    rate_change: float = 0.0            # prime-rate change


SCENARIOS = {
    "Conservative": Scenario(appt_change=-0.06, eff_change=-0.03, parts_cost_change=0.03, collect_change=0.15, opex_change=0.02, rate_change=0.005),
    "Base": Scenario(),
    "Optimistic": Scenario(appt_change=0.05, eff_change=0.05, parts_cost_change=-0.02, cycle_change=-0.10, collect_change=-0.10, expansion=0.10),
}
SCENARIO_NOTES = {
    "Conservative": "Demand -6%, technician efficiency -3%, parts cost +3%, collections 15% slower, opex +2%, prime +50 bps.",
    "Base": "Model forecasts of demand and technician capacity, TTM rates and cost ratios, current staffing plan and leases, prime flat.",
    "Optimistic": "Demand +5%, efficiency +5%, parts cost -2%, cycle time -10%, collections 10% faster, detailing & protection +10%.",
}
SCENARIO_FIELDS = [("eff_change", "Technician efficiency change", "%"), ("parts_cost_change", "Parts procurement cost change", "%"),
                   ("cycle_change", "Repair cycle-time change", "%"), ("appt_change", "Appointment volume change", "%"),
                   ("margin_change", "Gross-margin improvement (relative)", "%"), ("collect_change", "Receivable collection-delay change", "%"),
                   ("hires", "Additional collision technicians (from Dec-2026)", "#"), ("expansion", "Detailing & paint-protection expansion", "%"),
                   ("opex_change", "Controllable operating-expense change", "%"), ("rate_change", "Prime-rate change", "%")]
SENSITIVITIES = [  # the spec scenarios: label, field, value
    ("10% improvement in technician efficiency", "eff_change", 0.10), ("5% reduction in parts procurement costs", "parts_cost_change", -0.05),
    ("15% reduction in average repair cycle time", "cycle_change", -0.15), ("10% increase in appointment volume", "appt_change", 0.10),
    ("5% improvement in gross margin", "margin_change", 0.05), ("20% reduction in receivables collection delays", "collect_change", -0.20),
    ("Hire 2 additional collision technicians", "hires", 2.0), ("25% expansion of detailing & paint protection", "expansion", 0.25),
    ("Operating expenses -5%", "opex_change", -0.05), ("Prime rate +100 bps", "rate_change", 0.01),
]
FIXED_LABELS = {
    "rph_coll": "Collision revenue per billed body & paint hour (incl. parts, materials, sublet)", "rph_mech": "Mechanical revenue per billed mechanical hour",
    "ot_share": "Overtime capacity as share of regular capacity", "attrition": "Share of waiting collision backlog lost per month",
    "ot_cost_coll": "Overtime cost per billed collision hour (x1.5 loaded wage / efficiency)", "ot_cost_mech": "Overtime cost per billed mechanical hour",
    "hire_hours": "Billed hours per month from one added collision technician", "hire_cost": "Monthly loaded cost of one added collision technician",
    "exp_labour": "Installer / detailer labour per $ of expanded detailing & protection revenue", "adj_rate": "Discounts, short-pays & adjustments / service revenue",
    "parts_coll": "Parts cost / collision revenue", "parts_mech": "Parts cost / mechanical revenue", "parts_oth": "Parts cost / detailing, glass & other revenue",
    "mat_coll": "Paint & materials cost / collision revenue", "mat_oth": "Materials cost / detailing & other revenue", "sublet_coll": "Sublet cost / collision revenue",
    "sublet_mech": "Sublet cost / mechanical revenue", "warranty_ratio": "Warranty rework parts & sublet / net revenue", "card_rate": "Card processing fees / net revenue",
    "ins_share": "Insurer-billed share of net revenue", "dso_ins": "Insurer days outstanding (TTM)", "ar_other_ratio": "Card & fleet receivables, months of net revenue",
    "inv_months": "Parts inventory, months of parts cost", "mat_months": "Materials inventory, months of materials cost", "wip_days": "WIP days of cost of sales (TTM)",
    "dpo_sup": "Supplier payment days (parts & materials purchases)", "vendor_ap_ratio": "Sublet & vendor payables, months of sublet + taxable opex",
    "accrued_ratio": "Accrued payroll, months of payroll", "gst": "GST rate", "prime": "Prime rate", "rev_spread": "Revolver spread", "term_spread": "Term-loan spread (blended)",
    "rev_limit": "Revolver limit", "min_cash": "Minimum month-end cash", "target_cash": "Target cash after draw", "repay_above": "Repay revolver above", "step": "Draw/repay increment",
    "payout": "Dividend payout ratio", "cash_floor": "Cash floor after dividend", "new_capex_life": "Useful life of new capex (months)",
    "tax_small": "Small-business tax rate", "tax_general": "General tax rate", "sbd_limit": "Small-business limit",
}

ROWS = [  # key, label, section, template, phase (s = static row-by-row, d = dynamic month-by-month)
    ("coll_dem", "Collision demand - billed body & paint hours (forecast x volume change)", "Capacity", "{dem_coll_base}*(1+{$appt_change})", "s"),
    ("coll_cap", "Collision regular capacity - billed hours (capacity x efficiency + hires)", "Capacity",
     "{cap_coll_base}*(1+{$eff_change})+{$hires}*{is_hired}*{$hire_hours}*(1+{$eff_change})", "s"),
    ("coll_ot_cap", "Collision overtime capacity - billed hours", "Capacity", "{$ot_share}*{cap_coll_base}", "s"),
    ("mech_dem", "Mechanical demand - billed hours", "Capacity", "{dem_mech_base}*(1+{$appt_change})", "s"),
    ("mech_cap", "Mechanical regular capacity - billed hours", "Capacity", "{cap_mech_base}*(1+{$eff_change})", "s"),
    ("mech_ot_cap", "Mechanical overtime capacity - billed hours", "Capacity", "{$ot_share}*{cap_mech_base}", "s"),
    ("rev_detail", "Detailing revenue", "Income statement", "{rev_detail_base}*(1+{$appt_change})*(1+{$expansion})", "s"),
    ("rev_glass", "Glass repair revenue", "Income statement", "{rev_glass_base}*(1+{$appt_change})", "s"),
    ("rev_other", "Other service revenue (PDR, paint protection, ADAS, fees)", "Income statement", "{rev_other_base}*(1+{$appt_change})*(1+{$expansion})", "s"),
    ("staff", "Staff compensation", "Income statement", "-{staff_d}*(1+{$opex_change})", "s"),
    ("occupancy", "Occupancy (lease schedule, utilities)", "Income statement", "-{occupancy_d}", "s"),
    ("marketing", "Marketing & advertising", "Income statement", "-{marketing_d}*(1+{$opex_change})", "s"),
    ("g_and_a", "General & administrative", "Income statement", "-{ga_d}*(1+{$opex_change})", "s"),
    ("capex_cum", "Cumulative new capex (memo)", "Fixed assets", "{capex_cum[-1]}+{capex_d}", "s"),
    ("da", "Depreciation", "Income statement", "-({da_existing}+{capex_cum[-1]}/{$new_capex_life})", "s"),
    # ---- dynamic: capacity queue, revenue, costs, statements
    ("coll_queue", "Collision backlog carried in - billed hours", "Capacity", "{coll_backlog[-1]}*(1-{$attrition}*(1+{$cycle_change}))", "d"),
    ("coll_hours", "Collision billed hours delivered", "Capacity", "MIN({coll_dem}+{coll_queue},{coll_cap}+{coll_ot_cap})", "d"),
    ("coll_ot", "Collision overtime used - billed hours", "Capacity", "MAX(0,{coll_hours}-{coll_cap})", "d"),
    ("coll_backlog", "Collision backlog waiting at month end - billed hours", "Capacity", "{coll_dem}+{coll_queue}-{coll_hours}", "d"),
    ("mech_queue", "Mechanical backlog carried in - billed hours", "Capacity", "{mech_backlog[-1]}*(1-{$attrition}*(1+{$cycle_change}))", "d"),
    ("mech_hours", "Mechanical billed hours delivered", "Capacity", "MIN({mech_dem}+{mech_queue},{mech_cap}+{mech_ot_cap})", "d"),
    ("mech_ot", "Mechanical overtime used - billed hours", "Capacity", "MAX(0,{mech_hours}-{mech_cap})", "d"),
    ("mech_backlog", "Mechanical backlog waiting at month end - billed hours", "Capacity", "{mech_dem}+{mech_queue}-{mech_hours}", "d"),
    ("rev_collision", "Collision repair revenue", "Income statement", "{coll_hours}*{$rph_coll}", "d"),
    ("rev_mech", "Mechanical service revenue", "Income statement", "{mech_hours}*{$rph_mech}", "d"),
    ("gross_rev", "Service revenue", "Income statement", "{rev_collision}+{rev_mech}+{rev_detail}+{rev_glass}+{rev_other}", "d"),
    ("adjustments", "Less: discounts, insurer short-pays & adjustments", "Income statement", "-{$adj_rate}*{gross_rev}", "d"),
    ("net_rev", "Total net revenue", "Income statement", "{gross_rev}+{adjustments}", "d"),
    ("labour", "Technician labour (staffing plan + overtime + hires)", "Income statement",
     "-({payroll_tech_base}+{$hires}*{is_hired}*{$hire_cost}+{coll_ot}*{$ot_cost_coll}+{mech_ot}*{$ot_cost_mech}+{$expansion}*({rev_detail_base}+{rev_other_base})*{$exp_labour})", "d"),
    ("parts", "Parts", "Income statement", "-({rev_collision}*{$parts_coll}+{rev_mech}*{$parts_mech}+({rev_detail}+{rev_glass}+{rev_other})*{$parts_oth})*(1+{$parts_cost_change})", "d"),
    ("materials", "Paint & materials", "Income statement", "-({rev_collision}*{$mat_coll}+({rev_detail}+{rev_other})*{$mat_oth})", "d"),
    ("sublet", "Subcontractor costs (sublet repairs & towing)", "Income statement", "-({rev_collision}*{$sublet_coll}+{rev_mech}*{$sublet_mech})", "d"),
    ("warranty", "Warranty rework - parts & sublet", "Income statement", "-{$warranty_ratio}*{net_rev}", "d"),
    ("margin_uplift", "Gross-margin initiatives (scenario)", "Income statement", "{$margin_change}*({net_rev}+{labour}+{parts}+{materials}+{sublet}+{warranty})", "d"),
    ("cogs", "Cost of sales", "Income statement", "{labour}+{parts}+{materials}+{sublet}+{warranty}+{margin_uplift}", "d"),
    ("gross_profit", "Gross profit", "Income statement", "{net_rev}+{cogs}", "d"),
    ("shop_ops", "Shop operations (incl. card fees)", "Income statement", "-({shopops_d}*(1+{$opex_change})+{$card_rate}*{net_rev})", "d"),
    ("opex", "Operating expenses (before depreciation)", "Income statement", "{staff}+{occupancy}+{marketing}+{g_and_a}+{shop_ops}", "d"),
    ("ebitda", "EBITDA", "Income statement", "{gross_profit}+{opex}", "d"),
    ("ebit", "Operating income (EBIT)", "Income statement", "{ebitda}+{da}", "d"),
    ("interest", "Interest expense", "Income statement", "-({term_loan[-1]}*({$prime}+{$rate_change}+{$term_spread})+{revolver[-1]}*({$prime}+{$rate_change}+{$rev_spread}))/12", "d"),
    ("pbt", "Income before tax", "Income statement", "{ebit}+{interest}", "d"),
    ("ytd_pbt", "Fiscal YTD income before tax (memo)", "Tax", "IF({is_jan},0,{ytd_pbt[-1]})+{pbt}", "d"),
    ("lcf", "Loss carry-forward at 1 January (memo)", "Tax", "IF({is_jan},MAX(0,{lcf[-1]}-{ytd_pbt[-1]}),{lcf[-1]})", "d"),
    ("tax_ytd", "Fiscal YTD income tax (memo)", "Tax", "{$tax_small}*MIN(MAX(0,{ytd_pbt}-{lcf}),{$sbd_limit})+{$tax_general}*MAX(0,{ytd_pbt}-{lcf}-{$sbd_limit})", "d"),
    ("tax", "Income taxes", "Income statement", "-({tax_ytd}-IF({is_jan},0,{tax_ytd[-1]}))", "d"),
    ("net_income", "Net income", "Income statement", "{pbt}+{tax}", "d"),
    ("ytd_ni", "Fiscal YTD net income (memo)", "Tax", "IF({is_jan},0,{ytd_ni[-1]})+{net_income}", "d"),
    ("ar_insurer", "Insurer receivables", "Balance sheet", "{$dso_ins}*(1+{$collect_change})/30.4*{$ins_share}*{net_rev}*(1+{$gst})", "d"),
    ("ar_other", "Card settlements & fleet receivables", "Balance sheet", "{$ar_other_ratio}*(1+{$collect_change})*{net_rev}*(1+{$gst})", "d"),
    ("inventory", "Parts inventory", "Balance sheet", "-{$inv_months}*{parts}", "d"),
    ("materials_inv", "Paint & detailing materials", "Balance sheet", "-{$mat_months}*{materials}", "d"),
    ("wip", "Work in progress - unbilled repair jobs", "Balance sheet", "-{$wip_days}*(1+{$cycle_change})/30.4*{cogs}", "d"),
    ("purchases", "Parts & materials purchases at cost (memo)", "Working capital", "-{parts}-{materials}-{warranty}+{inventory}-{inventory[-1]}+{materials_inv}-{materials_inv[-1]}", "d"),
    ("prepaid", "Prepaid expenses", "Balance sheet", "{prepaid[-1]}+{insurance_premium}-{insurance_exp}", "d"),
    ("gst_remit", "GST remitted for prior quarter (memo)", "Working capital", "IF({q_start},{gst_net[-1]},0)", "d"),
    ("gst_net", "Net GST payable / (recoverable) (memo)", "Working capital",
     "{gst_net[-1]}+{$gst}*({net_rev}-{purchases}+{sublet}-{taxable_opex}-{capex_d})-{gst_remit}", "d"),
    ("ap", "Accounts payable (suppliers, sublet & vendors)", "Balance sheet",
     "{$dpo_sup}/30.4*{purchases}*(1+{$gst})+{$vendor_ap_ratio}*({taxable_opex}-{sublet})*(1+{$gst})", "d"),
    ("accrued", "Accrued payroll", "Balance sheet", "{$accrued_ratio}*(-{labour}-{staff})", "d"),
    ("prior_tax", "Prior-year tax awaiting payment (memo)", "Tax", "IF({is_jan},{tax_ytd[-1]},IF({is_mar},0,{prior_tax[-1]}))", "d"),
    ("tax_paid", "Income tax paid (memo)", "Tax", "IF({is_mar},{prior_tax[-1]},0)", "d"),
    ("tax_payable", "Income taxes payable", "Balance sheet", "{tax_payable[-1]}-{tax}-{tax_paid}", "d"),
    ("ppe_gross", "Fixed assets at cost", "Balance sheet", "{ppe_gross[-1]}+{capex_d}", "d"),
    ("acc_dep", "Accumulated depreciation", "Balance sheet", "{acc_dep[-1]}+{da}", "d"),
    ("cf_ni", "Net income", "Cash flow", "{net_income}", "d"),
    ("cf_da", "Depreciation", "Cash flow", "-{da}", "d"),
    ("d_ar", "(Increase) decrease in receivables", "Cash flow", "{ar_insurer[-1]}+{ar_other[-1]}-{ar_insurer}-{ar_other}", "d"),
    ("d_inv", "(Increase) decrease in parts & materials inventory", "Cash flow", "{inventory[-1]}+{materials_inv[-1]}-{inventory}-{materials_inv}", "d"),
    ("d_wip", "(Increase) decrease in work in progress", "Cash flow", "{wip[-1]}-{wip}", "d"),
    ("d_ap", "Increase (decrease) in supplier & vendor payables", "Cash flow", "{ap}-{ap[-1]}", "d"),
    ("d_other", "Other working capital (prepaid, accrued payroll, GST, tax)", "Cash flow",
     "{prepaid[-1]}-{prepaid}+{accrued}-{accrued[-1]}+{gst_net}-{gst_net[-1]}+{tax_payable}-{tax_payable[-1]}", "d"),
    ("cfo", "Net cash from operating activities", "Cash flow", "{cf_ni}+{cf_da}+{d_ar}+{d_inv}+{d_wip}+{d_ap}+{d_other}", "d"),
    ("cfi", "Capital expenditures", "Cash flow", "-{capex_d}", "d"),
    ("term_repay", "Term-loan principal repayments", "Cash flow", "-MIN({principal_d},{term_loan[-1]})", "d"),
    ("pre_cash", "Cash before revolver (memo)", "Cash flow", "{cash[-1]}+{cfo}+{cfi}+{term_repay}", "d"),
    ("rev_draw", "Borrowings (revolver draws)", "Cash flow", "IF({pre_cash}<{$min_cash},MIN({$rev_limit}-{revolver[-1]},CEIL(MAX(0,{$target_cash}-{pre_cash}),{$step})),0)", "d"),
    ("rev_repay", "Revolver repayments", "Cash flow", "IF(({pre_cash}>{$repay_above})*({revolver[-1]}>0),-MIN({revolver[-1]},FLOOR(MAX(0,{pre_cash}-{$target_cash}),{$step})),0)", "d"),
    ("revolver", "Revolving line of credit", "Balance sheet", "{revolver[-1]}+{rev_draw}+{rev_repay}", "d"),
    ("dividends", "Dividends paid", "Cash flow",
     "IF({is_dec}*({revolver}<0.005),-FLOOR(MIN({$payout}*MAX(0,{ytd_ni}),MAX(0,{pre_cash}+{rev_draw}+{rev_repay}-{$cash_floor})),1000),0)", "d"),
    ("cff", "Net cash from (used in) financing activities", "Cash flow", "{term_repay}+{rev_draw}+{rev_repay}+{dividends}", "d"),
    ("net_change", "Net change in cash", "Cash flow", "{cfo}+{cfi}+{cff}", "d"),
    ("cash", "Cash", "Balance sheet", "{cash[-1]}+{net_change}", "d"),
    ("term_loan", "Term-loan balance (memo)", "Balance sheet", "{term_loan[-1]}+{term_repay}", "d"),
    ("share_capital", "Share capital", "Balance sheet", "{share_capital[-1]}", "d"),
    ("cpe", "Current-year earnings", "Balance sheet", "IF({is_dec},0,{cpe[-1]}+{net_income})", "d"),
    ("retained", "Retained earnings", "Balance sheet", "{retained[-1]}+IF({is_dec},{cpe[-1]}+{net_income},0)+{dividends}", "d"),
    ("gst_rec", "GST recoverable", "Balance sheet", "MAX(0,-{gst_net})", "d"),
    ("current_assets", "Total current assets", "Balance sheet", "{cash}+{ar_insurer}+{ar_other}+{inventory}+{materials_inv}+{wip}+{prepaid}+{gst_rec}", "d"),
    ("ppe_net", "Net fixed assets", "Balance sheet", "{ppe_gross}+{acc_dep}", "d"),
    ("total_assets", "TOTAL ASSETS", "Balance sheet", "{current_assets}+{ppe_net}", "d"),
    ("gst_pay", "GST payable", "Balance sheet", "MAX(0,{gst_net})", "d"),
    ("term_current", "Current portion of term loans", "Balance sheet", "MIN({term_loan},{principal_next12})", "d"),
    ("current_liabilities", "Total current liabilities", "Balance sheet", "{ap}+{accrued}+{gst_pay}+{tax_payable}+{revolver}+{term_current}", "d"),
    ("term_lt", "Term loans (non-current)", "Balance sheet", "{term_loan}-{term_current}", "d"),
    ("total_liabilities", "TOTAL LIABILITIES", "Balance sheet", "{current_liabilities}+{term_lt}", "d"),
    ("total_equity", "TOTAL EQUITY", "Balance sheet", "{share_capital}+{retained}+{cpe}", "d"),
    ("total_le", "TOTAL LIABILITIES AND EQUITY", "Balance sheet", "{total_liabilities}+{total_equity}", "d"),
    ("working_capital", "Working capital (memo)", "Working capital", "{current_assets}-{current_liabilities}", "d"),
    ("check_bs", "Check: assets - liabilities - equity (must be 0)", "Checks", "{total_assets}-{total_le}", "d"),
    ("check_cash", "Check: ending cash - (opening cash + net change) (must be 0)", "Checks", "{cash}-{cash[-1]}-{net_change}", "d"),
]
ROW = {r[0]: r for r in ROWS}
DRIVER_ROWS = [("dem_coll_base", "Collision demand - billed body & paint hours (Model 2 RO-volume forecast x hours per RO)"),
               ("dem_mech_base", "Mechanical demand - billed hours (Model 2)"), ("cap_coll_base", "Collision technician capacity - billed hours (Model 5 x efficiency)"),
               ("cap_mech_base", "Mechanical technician capacity - billed hours (Model 5 x efficiency)"),
               ("rev_detail_base", "Detailing revenue (Model 1)"), ("rev_glass_base", "Glass revenue (Model 1)"), ("rev_other_base", "Other services revenue (Model 1)"),
               ("payroll_tech_base", "Technician payroll - staffing plan, regular & paid-absence hours (TTM same month +3%)"),
               ("staff_d", "Staff compensation plan"), ("occupancy_d", "Occupancy: lease schedule (+3% Jan) + utilities seasonal"),
               ("marketing_d", "Marketing plan"), ("ga_d", "General & administrative"), ("shopops_d", "Shop operations excl. card fees"),
               ("taxable_opex", "GST-taxable operating expenses (ITCs and vendor payables)"), ("insurance_exp", "Insurance expense"),
               ("insurance_premium", "Insurance premium paid (January)"), ("capex_d", "Capital expenditure plan"), ("da_existing", "Depreciation - existing asset register"),
               ("principal_d", "Scheduled term-loan principal"), ("principal_next12", "Scheduled principal due within 12 months"),
               ("is_hired", "Flag: new hires on staff (from Dec-2026)"), ("is_jan", "Flag: January"), ("is_mar", "Flag: March"), ("is_dec", "Flag: December"),
               ("q_start", "Flag: first month of quarter")]
OPENING = {"coll_backlog", "mech_backlog", "ar_insurer", "ar_other", "inventory", "materials_inv", "wip", "term_loan", "revolver", "prepaid", "gst_net", "ap", "accrued",
           "tax_payable", "ppe_gross", "acc_dep", "cash", "share_capital", "retained", "cpe", "ytd_pbt", "lcf", "tax_ytd", "prior_tax", "capex_cum", "ytd_ni"}
TOK = re.compile(r"\{(\$?)([a-z_0-9]+)(\[[+-]\d\]|@\d+)?\}")
ZERO = H + 1


def _py(template):
    def sub(m):
        dollar, key, suf = m.groups()
        if dollar:
            return f"A['{key}']"
        if not suf:
            return f"V['{key}'][t]"
        if suf.startswith("@"):
            return f"V['{key}'][{int(suf[1:])}]"
        return f"V['{key}'][W(t{int(suf[1:-1]):+d})]"
    return TOK.sub(sub, template)


FUN = dict(IF=lambda c, a, b: a if c else b, MAX=max, MIN=min, CEIL=lambda x, s: math.ceil(round(x / s, 9)) * s,
           FLOOR=lambda x, s: math.floor(round(x / s, 9)) * s, W=lambda i: ZERO if i < 0 else (i if i <= H else i - H))
COMPILED = {k: compile(_py(tpl), k, "eval") for k, _, _, tpl, _ in ROWS}


def run(sc: Scenario, base: dict) -> pd.DataFrame:
    A = dict(base["A"])
    A.update({k: float(getattr(sc, k)) for k in sc.__dataclass_fields__})
    V = {k: [0.0] * (H + 2) for k, *_ in ROWS}
    for k in base["drivers"].index:
        V[k] = [0.0] + list(map(float, base["drivers"].loc[k].values)) + [0.0]
    for k, v in base["opening"].items():
        V[k][0] = float(v)
    ns = dict(FUN, A=A, V=V)
    for k, _, _, _, ph in ROWS:
        if ph == "s":
            for t in range(1, H + 1):
                ns["t"] = t
                V[k][t] = eval(COMPILED[k], ns)
    for t in range(1, H + 1):
        ns["t"] = t
        for k, _, _, _, ph in ROWS:
            if ph == "d":
                V[k][t] = eval(COMPILED[k], ns)
    out = pd.DataFrame({k: V[k][:H + 1] for k, *_ in ROWS}).T
    out.columns = ["2026-09 (actual)"] + [str(m) for m in FC_MONTHS]
    return out


def summary(f):
    x = f.iloc[:, 1:]
    return {"net_revenue": x.loc["net_rev"].sum(), "gross_profit": x.loc["gross_profit"].sum(), "gross_margin_pct": x.loc["gross_profit"].sum() / x.loc["net_rev"].sum() * 100,
            "ebitda": x.loc["ebitda"].sum(), "operating_profit": x.loc["ebit"].sum(), "net_income": x.loc["net_income"].sum(),
            "net_margin_pct": x.loc["net_income"].sum() / x.loc["net_rev"].sum() * 100, "cfo": x.loc["cfo"].sum(), "closing_cash": x.loc["cash"].iloc[-1],
            "min_cash": x.loc["cash"].min(), "peak_revolver": max(0.0, x.loc["revolver"].max()), "closing_working_capital": x.loc["working_capital"].iloc[-1],
            "closing_wip": x.loc["wip"].iloc[-1], "closing_insurer_ar": x.loc["ar_insurer"].iloc[-1],
            "collision_hours": x.loc["coll_hours"].sum(), "collision_overtime_hours": x.loc["coll_ot"].sum(), "collision_unmet_hours": x.loc["coll_backlog"].iloc[-1],
            "mechanical_hours": x.loc["mech_hours"].sum(), "dividends": -x.loc["dividends"].sum(),
            "max_abs_bs_check": x.loc["check_bs"].abs().max(), "max_abs_cash_check": x.loc["check_cash"].abs().max()}


# ----------------------------------------------------------------------------------------------- calibration
def _fc(target):
    fc = pd.read_csv(TABLES / "forecast_next_12_months.csv", parse_dates=["month"])
    s = fc[fc.target == target].sort_values("month").forecast.values[:H]
    if len(s) < H:
        raise SystemExit(f"Missing forecast target {target}")
    return np.asarray(s, float)


def job_mix(T, months):
    """Operational job costing for delivered ROs in `months`: revenue & cost components by service line, billed hours by op group."""
    ro, inv = T["repair_orders"], T["customer_invoices"]
    d = ro[(ro.completion_date.dt.to_period("M").isin(months))]
    f = inv[inv.ro_id.isin(d.ro_id)].groupby("ro_id").agg(sub=("subtotal_cad", "sum"), lab=("labour_cad", "first"))
    mv = T["parts_inventory_movements"]
    iss = mv[mv.movement_type == "ISSUE_TO_RO"]
    parts = -iss[iss.inventory_state != "materials"].groupby("ro_id").value_cad.sum()
    mats = -iss[iss.inventory_state == "materials"].groupby("ro_id").value_cad.sum()
    sub = T["sublet_lines"].groupby("ro_id").cost_cad.sum()
    x = d.set_index("ro_id").assign(rev=f["sub"], parts=parts, mats=mats, sublet=sub).fillna({"rev": 0, "parts": 0, "mats": 0, "sublet": 0})
    return x


def calibrate(L, St, K):
    T = L["T"]
    is_m, bal = St["is_m"], St["bal"]
    ttm = [str(m) for m in TTM]
    t = is_m[ttm].sum(axis=1)
    x = job_mix(T, TTM)
    nw = x[x.payer_type != "Warranty (internal)"]
    line = nw.groupby("service_line")[["rev", "parts", "mats", "sublet"]].sum()
    coll_h = nw[nw.service_line == "Collision repair"][["billed_body_hours", "billed_paint_hours"]].sum().sum()
    mech_h = nw[nw.service_line == "Mechanical service"].billed_mech_hours.sum()
    A = {}
    A["rph_coll"] = float(t["rev_collision"] / coll_h)
    A["rph_mech"] = float(t["rev_mech"] / mech_h)
    # cost ratios by line from job costing, scaled so the total equals the GL for the TTM
    raw = {"parts": line.parts, "mats": line.mats, "sublet": line.sublet}
    gl_tot = {"parts": -t["parts"], "mats": -t["materials"], "sublet": -t["sublet"]}
    sc = {k: gl_tot[k] / max(raw[k].sum(), 1) for k in raw}
    rv = line.rev
    oth = ["Detailing", "Glass repair", "Other services"]
    A["parts_coll"] = float(raw["parts"]["Collision repair"] * sc["parts"] / rv["Collision repair"])
    A["parts_mech"] = float(raw["parts"]["Mechanical service"] * sc["parts"] / rv["Mechanical service"])
    A["parts_oth"] = float(raw["parts"][oth].sum() * sc["parts"] / rv[oth].sum())
    A["mat_coll"] = float(raw["mats"]["Collision repair"] * sc["mats"] / rv["Collision repair"])
    A["mat_oth"] = float(raw["mats"][["Detailing", "Other services"]].sum() * sc["mats"] / rv[["Detailing", "Other services"]].sum())
    A["sublet_coll"] = float(raw["sublet"]["Collision repair"] * sc["sublet"] / rv["Collision repair"])
    A["sublet_mech"] = float(raw["sublet"].get("Mechanical service", 0) * sc["sublet"] / rv["Mechanical service"])
    A["adj_rate"] = float(-t["adjustments"] / t["gross_rev"])
    A["warranty_ratio"] = float(-(t["warranty"] + t["inv_adj"]) / t["net_rev"])
    # overtime and hiring economics (collision techs: body & paint roles)
    ts = T["technician_timesheets"].merge(T["technicians"][["tech_id", "role", "op_groups"]], on="tech_id")
    tt = ts[ts.work_date.dt.to_period("M").isin(TTM)]
    coll_t = tt[tt.op_groups.str.contains("BODY|PAINT")]
    mech_t = tt[tt.op_groups.str.contains("MECH") & ~tt.op_groups.str.contains("BODY|PAINT")]
    asg = T["job_assignments"]
    at = asg[asg.work_date.dt.to_period("M").isin(TTM)]
    eff_c = coll_h / at[at.operation.isin(["BODY", "PAINT"]) & at.ro_id.isin(nw[nw.service_line == "Collision repair"].index)].clocked_hours.sum()
    eff_m = mech_h / at[(at.operation == "MECH") & at.ro_id.isin(nw[nw.service_line == "Mechanical service"].index)].clocked_hours.sum()
    A["eff_coll_ttm"], A["eff_mech_ttm"] = float(eff_c), float(eff_m)
    w_c, w_m = coll_t.hourly_wage_cad.mean() * 1.03, mech_t.hourly_wage_cad.mean() * 1.03
    A["ot_cost_coll"] = float(w_c * P.OT_PREMIUM * (1 + P.LABOUR_BURDEN) / eff_c)
    A["ot_cost_mech"] = float(w_m * P.OT_PREMIUM * (1 + P.LABOUR_BURDEN) / eff_m)
    A["ot_share"] = 0.10
    A["attrition"] = 0.15
    per_tech_avail = coll_t.groupby(["tech_id", coll_t.work_date.dt.to_period("M")]).available_hours.sum().mean()
    A["hire_hours"] = float(per_tech_avail * 0.88 * eff_c)
    A["hire_cost"] = float(coll_t.groupby(["tech_id", coll_t.work_date.dt.to_period("M")]).scheduled_hours.sum().mean() * w_c * (1 + P.LABOUR_BURDEN))
    det = at[at.operation.isin(["DETAIL", "PPF"])].labour_cost_cad.sum()
    A["exp_labour"] = float(det / rv[["Detailing", "Other services"]].sum())
    gl = L["gl"]
    A["card_rate"] = float(gl[(gl.account == "6430") & gl.month.isin(TTM) & ~gl.is_closing].amount.sum() / t["net_rev"])
    # working capital (13-point averages on the TTM)
    b = bal.loc[[TTM[0] - 1] + list(TTM)]
    inv = T["customer_invoices"]
    ins_bill = inv[(inv.bill_to_type == "Insurer") & inv.invoice_date.dt.to_period("M").isin(TTM)].subtotal_cad.sum()
    A["ins_share"] = float(ins_bill / t["net_rev"])
    A["dso_ins"] = float(b["1110"].mean() / (ins_bill * (1 + P.GST_RATE)) * 365)
    A["ar_other_ratio"] = float(b[["1100", "1120"]].sum(axis=1).mean() / (t["net_rev"] / 12 * (1 + P.GST_RATE)))
    A["inv_months"] = float(b[["1200", "1210"]].sum(axis=1).mean() / (-t["parts"] / 12))
    A["mat_months"] = float(b["1220"].mean() / (-t["materials"] / 12))
    A["wip_days"] = float(b["1250"].mean() / (-t["cogs"] / 12) * 30.4)
    po = T["supplier_purchase_orders"]
    rec = po[po.received_date.dt.to_period("M").isin(TTM)]
    purch = (rec.qty_ordered * rec.unit_cost_cad).sum()
    A["dpo_sup"] = float(-b["2000"].mean() / (purch / 12 * (1 + P.GST_RATE)) * 30.4)
    o = T["operating_expenses"]
    oo = o[o.month.dt.to_period("M").isin(TTM)]
    taxable = sum(oo[c].sum() for c, a_br, a_ho, v, k in P.OPEX_MAP if k == "vendor" and a_br in P.GST_TAXABLE_OPEX)
    A["vendor_ap_ratio"] = float(-b["2010"].mean() / ((taxable + T["sublet_lines"][T["sublet_lines"].sublet_date.dt.to_period("M").isin(TTM)].cost_cad.sum()) / 12 * (1 + P.GST_RATE)))
    A["accrued_ratio"] = 1 - P.PAYROLL_FIRST_HALF
    A["gst"] = P.GST_RATE
    A["prime"] = float(prime_rate(T["econ"]).loc[pd.Period(END, "M")])
    tl = L["treasury"].set_index("month")
    bals = {lid: float(tl.at[END[:7], f"balance_{lid}"]) for lid, *_ in P.LOANS}
    A["term_spread"] = float(sum(bals[l] * s for l, _, _, _, _, s in P.LOANS) / max(sum(bals.values()), 1))
    A["rev_spread"] = P.REVOLVER["spread"]
    for k in ["limit", "min_cash", "target_cash", "repay_above", "step"]:
        A[{"limit": "rev_limit"}.get(k, k)] = P.REVOLVER[k]
    A["payout"], A["cash_floor"] = P.DIVIDEND["payout"], P.DIVIDEND["cash_floor"]
    A["new_capex_life"] = 120.0
    A["tax_small"], A["tax_general"], A["sbd_limit"] = P.TAX_SMALL_RATE, P.TAX_GENERAL_RATE, P.SMALL_BUSINESS_LIMIT
    return {k: float(v) for k, v in A.items()}


def drivers(L, St, A):
    T = L["T"]
    same = [str(m - 12) for m in FC_MONTHS]
    cap_c = _fc("tech_available_hours_collision") * 0.88 * A["eff_coll_ttm"]
    cap_m = _fc("tech_available_hours_mechanical") * 0.88 * A["eff_mech_ttm"]
    ts = T["technician_timesheets"].merge(T["technicians"][["tech_id", "termination_date"]], on="tech_id")
    ts["m"] = ts.work_date.dt.to_period("M").astype(str)
    active = ts.termination_date.isna() | (ts.termination_date > pd.Timestamp(END))
    reg = (ts.scheduled_hours * ts.hourly_wage_cad * (1 + P.LABOUR_BURDEN))[active].groupby(ts.m[active]).sum()
    payroll = np.array([reg.get(m, reg.iloc[-12:].mean()) * 1.03 for m in same])
    o = T["operating_expenses"].assign(m=lambda x: x.month.dt.to_period("M").astype(str))
    g = o.groupby("m").sum(numeric_only=True)
    staff = np.array([g.at[m, "staff_wages_cad"] * 1.03 for m in same])
    rent_sep = g.loc[END[:7], ["rent_cad", "cam_property_tax_cad"]].sum()
    occ = np.array([rent_sep * (1.03 if m.year == 2027 else 1.0) + g.at[sm, "utilities_cad"] * 1.025 for m, sm in zip(FC_MONTHS, same)])
    mkt = np.array([g.at[m, "marketing_cad"] * 1.025 for m in same])
    ga_cols = ["insurance_cad", "professional_fees_cad", "software_it_cad", "network_certification_fees_cad", "training_certification_cad"]
    ga = np.array([g.loc[m, ga_cols].sum() * 1.025 for m in same])
    shop_cols = ["shop_supplies_cad", "equipment_maintenance_cad", "courtesy_vehicles_concierge_cad", "courier_waste_cad"]
    shop = np.array([g.loc[m, shop_cols].sum() * 1.025 for m in same])
    taxable = occ + mkt + np.array([g.loc[m, ["professional_fees_cad", "software_it_cad", "network_certification_fees_cad", "training_certification_cad"]].sum() * 1.025
                                    for m in same]) + shop
    ins_sep = g.at[END[:7], "insurance_cad"]
    ins = np.array([ins_sep * (1.04 if m.year == 2027 else 1.0) for m in FC_MONTHS])
    prem = np.array([ins_sep * 1.04 * 12 if m.month == 1 else 0.0 for m in FC_MONTHS])
    capex = np.array([60000.0 if str(m) == "2027-03" else 0.0 for m in FC_MONTHS])
    dep = fixed_asset_schedule(until="2027-09")
    da = dep.groupby("month").depreciation.sum().reindex(FC_MONTHS, fill_value=0.0).values
    ls = loan_schedule()
    pr = ls.groupby("month").principal.sum()
    principal = pr.reindex(FC_MONTHS, fill_value=0.0).values
    nxt = np.array([ls[(ls.month > m) & (ls.month <= m + 12)].principal.sum() for m in FC_MONTHS])
    return pd.DataFrame({"dem_coll_base": _fc("billed_hours_collision"), "dem_mech_base": _fc("billed_hours_mechanical"), "cap_coll_base": cap_c, "cap_mech_base": cap_m,
                         "rev_detail_base": _fc("revenue_detailing"), "rev_glass_base": _fc("revenue_glass"), "rev_other_base": _fc("revenue_other"),
                         "payroll_tech_base": payroll, "staff_d": staff, "occupancy_d": occ, "marketing_d": mkt, "ga_d": ga, "shopops_d": shop, "taxable_opex": taxable,
                         "insurance_exp": ins, "insurance_premium": prem, "capex_d": capex, "da_existing": da, "principal_d": principal, "principal_next12": nxt,
                         "is_hired": [int(i >= 2) for i in range(H)], "is_jan": [int(m.month == 1) for m in FC_MONTHS], "is_mar": [int(m.month == 3) for m in FC_MONTHS],
                         "is_dec": [int(m.month == 12) for m in FC_MONTHS], "q_start": [int(m.month in (1, 4, 7, 10)) for m in FC_MONTHS]}, index=range(1, H + 1)).T


def opening_values(L, St, A):
    b = St["bal"].loc[pd.Period(END, "M")]
    T = L["T"]
    tr = L["treasury"].set_index("month")
    is26 = St["is_m"][[c for c in St["is_m"].columns if c.startswith("2026")]]
    ro = T["repair_orders"]
    op = ro[~(ro.completion_date <= pd.Timestamp(END)) & (ro.payer_type != "Warranty (internal)")]
    clk = T["job_assignments"].groupby(["ro_id", "operation"]).clocked_hours.sum().unstack(fill_value=0.0)
    c = op[op.service_line == "Collision repair"].set_index("ro_id")
    rem_c = (c.billed_body_hours + c.billed_paint_hours - clk.reindex(c.index).fillna(0)[["BODY", "PAINT"]].sum(axis=1) * A["eff_coll_ttm"]).clip(lower=0).sum()
    m = op[op.service_line == "Mechanical service"].set_index("ro_id")
    rem_m = (m.billed_mech_hours - clk.reindex(m.index).fillna(0).get("MECH", 0) * A["eff_mech_ttm"]).clip(lower=0).sum()
    return {"coll_backlog": float(rem_c), "mech_backlog": float(rem_m), "ar_insurer": b["1110"], "ar_other": b["1100"] + b["1120"], "inventory": b["1200"] + b["1210"],
            "materials_inv": b["1220"], "wip": b["1250"], "term_loan": -b["2700"], "revolver": -b["2600"], "prepaid": b["1300"], "gst_net": -(b["1400"] + b["2300"]),
            "ap": -(b["2000"] + b["2010"]), "accrued": -b["2100"], "tax_payable": -b["2400"], "ppe_gross": b[["1500", "1510", "1520", "1530"]].sum(), "acc_dep": b["1590"],
            "cash": b["1000"], "share_capital": -b["3000"], "retained": -(b["3200"] + b["3300"]), "cpe": St["bs_m"].at["cpe", END[:7]], "ytd_pbt": is26.loc["pbt"].sum(),
            "lcf": float(tr.at[END[:7], "loss_carryforward"]), "tax_ytd": -is26.loc["tax"].sum(), "prior_tax": 0.0, "capex_cum": 0.0, "ytd_ni": is26.loc["net_income"].sum()}


def sensitivity(base):
    b = summary(run(SCENARIOS["Base"], base))
    rows = []
    for lab, fld, val in SENSITIVITIES:
        r = summary(run(replace(SCENARIOS["Base"], **{fld: val}), base))
        rows.append({"scenario": lab, "driver": fld, "value": val, "delta_net_revenue": r["net_revenue"] - b["net_revenue"], "delta_gross_profit": r["gross_profit"] - b["gross_profit"],
                     "delta_operating_profit": r["operating_profit"] - b["operating_profit"], "delta_net_income": r["net_income"] - b["net_income"],
                     "delta_cfo": r["cfo"] - b["cfo"], "delta_closing_cash": r["closing_cash"] - b["closing_cash"],
                     "delta_working_capital": r["closing_working_capital"] - b["closing_working_capital"],
                     "delta_collision_hours": r["collision_hours"] - b["collision_hours"], "delta_overtime_hours": r["collision_overtime_hours"] - b["collision_overtime_hours"],
                     "net_income": r["net_income"], "closing_cash": r["closing_cash"]})
    return pd.DataFrame(rows)


def build(L, St, K=None):
    A = calibrate(L, St, K)
    base = {"A": A, "opening": opening_values(L, St, A)}
    base["drivers"] = drivers(L, St, A)
    res = {n: run(sc, base) for n, sc in SCENARIOS.items()}
    summ = pd.DataFrame({k: summary(v) for k, v in res.items()}).T
    summ["assumptions"] = pd.Series(SCENARIO_NOTES)
    return dict(base=base, results=res, summary=summ, sensitivity=sensitivity(base))
