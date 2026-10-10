"""Trial balances, the integrated three statements (consolidated) and branch income statements, derived ONLY from
general-ledger balances (SIMULATED).

Presentation: income-statement and cash-flow lines are signed (+ income / inflow, - cost / outflow); balance-sheet lines are
positive balances, with accumulated depreciation shown negative. Interbranch revenue (4950) and cost (5450) appear in the branch
statements and are eliminated in the consolidated statements.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import END
from src.finance import policy as P
from src.finance.ledger import MONTHS, fixed_asset_schedule, labour_wip_at, loan_schedule, wip_components

ALL_M = pd.period_range("2023-12", END, freq="M")
BRANCHES = ["BR-SEC", "BR-CCC", "BR-NFS"]


def activity(gl, include_closing=True):
    g = gl if include_closing else gl[~gl.is_closing]
    a = g.groupby(["month", "account"]).amount.sum().unstack(fill_value=0.0)
    return a.reindex(index=ALL_M, columns=list(P.ACCOUNTS), fill_value=0.0)


def balances(gl):
    return activity(gl).cumsum().round(2)


def trial_balances(gl):
    act = activity(gl, include_closing=False)
    pre = act.cumsum()
    yrs = [m.year for m in act.index]
    for a, v in P.ACCOUNTS.items():
        if v["type"] in P.PNL_TYPES or a == "3300":
            pre[a] = act[a].groupby(yrs).cumsum()
    pre["3200"] = activity(gl)["3200"].cumsum() - activity(gl[gl.is_closing])["3200"].groupby(yrs).cumsum()
    pre = pre.round(2)
    rows = [{"month": str(m), "account": a, "account_name": P.ACCOUNTS[a]["name"], "type": P.ACCOUNTS[a]["type"],
             "debit": round(v, 2) if v > 0 else 0.0, "credit": round(-v, 2) if v < 0 else 0.0}
            for m in pre.index for a in P.ACCOUNTS if abs(v := pre.at[m, a]) >= 0.005]
    return pd.DataFrame(rows).assign(data_status="SIMULATED")


IS_LINES = [  # key, label, accounts, kind
    ("rev_collision", "Collision repair revenue", ["4000"], "rev"), ("rev_mech", "Mechanical service revenue", ["4100"], "rev"),
    ("rev_detail", "Detailing revenue", ["4200"], "rev"), ("rev_glass", "Glass repair revenue", ["4300"], "rev"),
    ("rev_other", "Other service revenue (PDR, paint protection, ADAS, fees)", ["4400"], "rev"),
    ("gross_rev", "Service revenue", None, "sub"),
    ("adjustments", "Less: discounts, insurer short-pays & adjustments", ["4900"], "cost"),
    ("net_rev", "Total net revenue", None, "sub"),
    ("labour", "Technician labour (wages, overtime & burden)", ["5000"], "cost"), ("parts", "Parts", ["5100"], "cost"),
    ("materials", "Paint & materials", ["5200"], "cost"), ("sublet", "Subcontractor costs (sublet repairs & towing)", ["5300"], "cost"),
    ("warranty", "Warranty rework - parts & sublet", ["5400"], "cost"), ("inv_adj", "Inventory adjustments & obsolescence", ["5500"], "cost"),
    ("cogs", "Cost of sales", None, "sub"),
    ("gross_profit", "Gross profit", None, "sub"),
    ("staff", "Staff compensation (branch & group)", ["6000", "6010"], "cost"),
    ("occupancy", "Occupancy (rent, CAM & property tax, utilities)", ["6100", "6105", "6110"], "cost"),
    ("marketing", "Marketing & advertising", ["6200"], "cost"),
    ("g_and_a", "General & administrative (insurance, professional, software, network, training)", ["6300", "6310", "6320", "6330", "6340"], "cost"),
    ("shop_ops", "Shop operations (supplies, maintenance, courtesy vehicles, courier & waste, card fees)", ["6400", "6410", "6420", "6430"], "cost"),
    ("opex", "Operating expenses (before depreciation)", None, "sub"),
    ("ebitda", "EBITDA", None, "sub"),
    ("da", "Depreciation", ["6900"], "cost"),
    ("ebit", "Operating income (EBIT)", None, "sub"),
    ("interest", "Interest expense", ["7000", "7010"], "cost"),
    ("pbt", "Income before tax", None, "sub"),
    ("tax", "Income taxes", ["8000"], "cost"),
    ("net_income", "Net income", None, "sub"),
]
IS_LABEL = {k: l for k, l, *_ in IS_LINES}
IS_SUB = {"gross_rev": ["rev_collision", "rev_mech", "rev_detail", "rev_glass", "rev_other"], "net_rev": ["gross_rev", "adjustments"],
          "cogs": ["labour", "parts", "materials", "sublet", "warranty", "inv_adj"], "gross_profit": ["net_rev", "cogs"],
          "opex": ["staff", "occupancy", "marketing", "g_and_a", "shop_ops"], "ebitda": ["gross_profit", "opex"], "ebit": ["ebitda", "da"],
          "pbt": ["ebit", "interest"], "net_income": ["pbt", "tax"]}


def _is_from_activity(a):
    out = {k: -a[accts].sum(axis=1) for k, _, accts, _ in IS_LINES if accts}
    for k, parts in IS_SUB.items():
        out[k] = sum(out[p] for p in parts)
    return out


def income_statement(gl):
    a = activity(gl, include_closing=False).loc[MONTHS[0]:]
    df = pd.DataFrame(_is_from_activity(a)).T.loc[[k for k, *_ in IS_LINES]].round(2)
    df.columns = [str(c) for c in df.columns]
    return df


def common_size(is_df):
    nr = is_df.loc["net_rev"].replace(0, np.nan)
    return (is_df / nr * 100).round(2)


BS_LINES = [
    ("cash", "Cash", "Current assets"), ("ar_insurer", "Insurer receivables (direct billing)", "Current assets"),
    ("ar_other", "Card settlements & fleet receivables", "Current assets"), ("inventory", "Parts inventory (stocked & special-order)", "Current assets"),
    ("materials", "Paint & detailing materials", "Current assets"), ("wip", "Work in progress - unbilled repair jobs (at cost)", "Current assets"),
    ("prepaid", "Prepaid expenses", "Current assets"), ("gst_rec", "GST recoverable", "Current assets"),
    ("current_assets", "Total current assets", "sub"),
    ("ppe_gross", "Fixed assets at cost", "Non-current"), ("acc_dep", "Accumulated depreciation", "Non-current"), ("ppe_net", "Net fixed assets", "sub"),
    ("total_assets", "TOTAL ASSETS", "sub"),
    ("ap", "Accounts payable (suppliers, sublet & vendors)", "Current liabilities"), ("accrued", "Accrued payroll", "Current liabilities"),
    ("gst_pay", "GST payable", "Current liabilities"), ("tax_payable", "Income taxes payable", "Current liabilities"),
    ("revolver", "Revolving line of credit", "Current liabilities"), ("term_current", "Current portion of term loans", "Current liabilities"),
    ("current_liabilities", "Total current liabilities", "sub"),
    ("term_lt", "Term loans (non-current)", "Non-current"), ("total_liabilities", "TOTAL LIABILITIES", "sub"),
    ("share_capital", "Share capital", "Equity"), ("retained", "Retained earnings", "Equity"), ("cpe", "Current-year earnings", "Equity"),
    ("total_equity", "TOTAL EQUITY", "sub"), ("total_le", "TOTAL LIABILITIES AND EQUITY", "sub"), ("check", "Check: assets - liabilities - equity", "check"),
]
BS_LABEL = {k: l for k, l, _ in BS_LINES}
BS_SUB = {"current_assets": ["cash", "ar_insurer", "ar_other", "inventory", "materials", "wip", "prepaid", "gst_rec"], "ppe_net": ["ppe_gross", "acc_dep"],
          "total_assets": ["current_assets", "ppe_net"], "current_liabilities": ["ap", "accrued", "gst_pay", "tax_payable", "revolver", "term_current"],
          "total_liabilities": ["current_liabilities", "term_lt"], "total_equity": ["share_capital", "retained", "cpe"], "total_le": ["total_liabilities", "total_equity"]}


def current_portion(index):
    s = loan_schedule()
    out = []
    for m in index:
        out.append(s[(s.month > m) & (s.month <= m + 12)].principal.sum())
    return pd.Series(out, index=index)


def balance_sheet(gl):
    b = balances(gl)
    pnl = [a for a, v in P.ACCOUNTS.items() if v["type"] in P.PNL_TYPES]
    o = {"cash": b["1000"], "ar_insurer": b["1110"], "ar_other": b[["1100", "1120"]].sum(axis=1), "inventory": b[["1200", "1210"]].sum(axis=1),
         "materials": b["1220"], "wip": b["1250"], "prepaid": b["1300"]}
    gst = b["1400"] + b["2300"]
    o["gst_rec"] = gst.clip(lower=0)
    o["ppe_gross"] = b[["1500", "1510", "1520", "1530"]].sum(axis=1)
    o["acc_dep"] = b["1590"]
    o["ap"] = -b[["2000", "2010"]].sum(axis=1)
    o["accrued"] = -b["2100"]
    o["gst_pay"] = (-gst).clip(lower=0)
    o["tax_payable"] = -b["2400"]
    o["revolver"] = -b["2600"]
    term = -b["2700"]
    o["term_current"] = np.minimum(term, current_portion(b.index).values)
    o["term_lt"] = term - o["term_current"]
    o["share_capital"] = -b["3000"]
    o["retained"] = -(b["3200"] + b["3300"])
    o["cpe"] = -b[pnl].sum(axis=1)
    for k, parts in BS_SUB.items():
        o[k] = sum(o[p] for p in parts)
    o["check"] = o["total_assets"] - o["total_le"]
    df = pd.DataFrame(o).T.loc[[k for k, *_ in BS_LINES]].round(2)
    df.columns = [str(c) for c in df.columns]
    return df


CF_LINES = [
    ("net_income", "Net income", "Operating"), ("da", "Depreciation", "Operating"),
    ("d_ar", "(Increase) decrease in receivables (insurer, fleet, card)", "Operating"),
    ("d_inv", "(Increase) decrease in parts & materials inventory", "Operating"),
    ("d_wip", "(Increase) decrease in work in progress", "Operating"),
    ("d_ap", "Increase (decrease) in supplier & vendor payables", "Operating"),
    ("d_other", "Other working capital (prepaid, accrued payroll, GST, tax)", "Operating"),
    ("cfo", "Net cash from operating activities", "sub"),
    ("capex", "Capital expenditures", "Investing"), ("cfi", "Net cash used in investing activities", "sub"),
    ("borrowings", "Borrowings (equipment loan & revolver draws)", "Financing"), ("repayments", "Debt repayments (loan principal & revolver)", "Financing"),
    ("dividends", "Dividends paid", "Financing"), ("cff", "Net cash from (used in) financing activities", "sub"),
    ("net_change", "Net change in cash", "sub"), ("open_cash", "Opening cash", "sub"), ("close_cash", "Ending cash balance", "sub"),
    ("bs_cash", "Cash per balance sheet", "check"), ("check", "Check: ending cash - balance-sheet cash", "check"),
]
CF_LABEL = {k: l for k, l, _ in CF_LINES}
CF_SUB = {"cfo": ["net_income", "da", "d_ar", "d_inv", "d_wip", "d_ap", "d_other"], "cfi": ["capex"], "cff": ["borrowings", "repayments", "dividends"],
          "net_change": ["cfo", "cfi", "cff"]}


def cash_flow(gl, is_df):
    act = activity(gl).loc[MONTHS[0]:]
    nc = gl[~gl.is_closing]

    def flow(acct, side):
        return nc[nc.account == acct].groupby("month")[side].sum().reindex(MONTHS, fill_value=0.0).values

    o = {"net_income": is_df.loc["net_income"].values, "da": -is_df.loc["da"].values,
         "d_ar": -act[["1100", "1110", "1120"]].sum(axis=1).values, "d_inv": -act[["1200", "1210", "1220"]].sum(axis=1).values,
         "d_wip": -act["1250"].values, "d_ap": -act[["2000", "2010"]].sum(axis=1).values,
         "d_other": -act[["1300", "1400", "2100", "2300", "2400"]].sum(axis=1).values,
         "capex": -act[["1500", "1510", "1520", "1530"]].sum(axis=1).values,
         "borrowings": flow("2600", "credit") + flow("2700", "credit"), "repayments": -(flow("2600", "debit") + flow("2700", "debit")),
         "dividends": -flow("3300", "debit")}
    for k, parts in CF_SUB.items():
        o[k] = sum(o[p] for p in parts)
    bs_cash = balances(gl)["1000"]
    o["open_cash"] = bs_cash.shift(1).loc[MONTHS[0]:].values
    o["close_cash"] = o["open_cash"] + o["net_change"]
    o["bs_cash"] = bs_cash.loc[MONTHS[0]:].values
    o["check"] = o["close_cash"] - o["bs_cash"]
    return pd.DataFrame(o, index=[str(m) for m in MONTHS]).T.loc[[k for k, *_ in CF_LINES]].round(2)


DIRECT = {"Invoicing": "Receipts at pickup (e-transfer)", "Collections": "Receipts: card settlements, insurer & fleet EFTs",
          "Supplier payments": "Payments to parts suppliers, sublet & operating vendors", "Operating expenses": "Rent & occupancy paid", "Payroll": "Payroll paid",
          "Prepaid expenses": "Insurance premiums paid", "GST remittance": "GST remitted", "Income tax": "Income tax paid",
          "Financing": "Interest, loan principal, loan draws & revolver", "Capital expenditure": "Capital expenditures", "Equity": "Dividends"}


def direct_cash_flow(gl):
    c = gl[(gl.account == "1000") & (gl.date > pd.Timestamp(P.OB_DATE))]
    d = c.assign(category=c.source.map(DIRECT)).pivot_table(index="category", columns="month", values="amount", aggfunc="sum", fill_value=0.0)
    d.columns = [str(x) for x in d.columns]
    return d.reindex(columns=[str(m) for m in MONTHS], fill_value=0.0).round(2)


def aggregate(is_df, bs_df, cf_df, freq):
    per = pd.PeriodIndex(is_df.columns, freq="M")
    key = per.asfreq("Q").astype(str) if freq == "Q" else per.year.astype(str)
    agg_is = is_df.T.groupby(key.values).sum().T
    agg_cf = cf_df.T.groupby(key.values).sum().T
    last = pd.Series(is_df.columns, index=key.values).groupby(level=0).last()
    first = pd.Series(is_df.columns, index=key.values).groupby(level=0).first()
    agg_cf.loc["open_cash"] = [cf_df.at["open_cash", first[k]] for k in agg_cf.columns]
    for r in ["close_cash", "bs_cash", "check"]:
        agg_cf.loc[r] = [cf_df.at[r, last[k]] for k in agg_cf.columns]
    agg_bs = bs_df[[last[k] for k in agg_is.columns]]
    agg_bs.columns = agg_is.columns
    return agg_is.round(2), agg_bs.round(2), agg_cf.round(2)


# ----------------------------------------------------------------------------------------------- branch statements
def branch_income_statements(gl, T):
    """Monthly income statement per branch (direct) + HO, with interbranch lines, and allocation of shared HO costs by documented drivers.
    Returns a long frame: month, branch_id, line, direct, allocated, total."""
    nc = gl[~gl.is_closing & gl.month.isin(MONTHS)]
    pnl = [a for a, v in P.ACCOUNTS.items() if v["type"] in P.PNL_TYPES]
    act = nc[nc.account.isin(pnl)].groupby(["month", "branch_id", "account"]).amount.sum().unstack(fill_value=0.0).reindex(columns=pnl, fill_value=0.0)
    rows = []
    # allocation drivers per month
    ext = act[[P.REV_ACCT[l] for l in P.REV_ACCT] + ["4900"]].sum(axis=1).mul(-1).unstack("branch_id").reindex(columns=BRANCHES, fill_value=0.0)
    bays = pd.Series({b[0]: b[5] for b in __import__("src.generate.params", fromlist=["BRANCHES"]).BRANCHES})
    ts = T["technician_timesheets"]
    hc = ts[ts.scheduled_hours > 0].groupby([ts.work_date.dt.to_period("M"), "branch_id"]).tech_id.nunique().unstack(fill_value=0).reindex(columns=BRANCHES, fill_value=0)
    for m in MONTHS:
        open_b = [b for b in BRANCHES if (m, b) in act.index]
        sh = {}
        r = ext.loc[m] if m in ext.index else pd.Series(0.0, index=BRANCHES)
        sh["revenue"] = (r.clip(lower=0) / r.clip(lower=0).sum()) if r.clip(lower=0).sum() else pd.Series(1 / 3, index=BRANCHES)
        bb = bays[[b for b in BRANCHES if b in open_b]]
        sh["bays"] = (bb / bb.sum()).reindex(BRANCHES, fill_value=0.0)
        h = hc.loc[m] if m in hc.index else pd.Series(0, index=BRANCHES)
        sh["headcount"] = (h / h.sum()) if h.sum() else sh["revenue"]
        sh["direct"] = sh["headcount"]
        ho = act.loc[(m, P.HO)] if (m, P.HO) in act.index else pd.Series(0.0, index=pnl)
        for b in BRANCHES:
            d = act.loc[(m, b)] if (m, b) in act.index else pd.Series(0.0, index=pnl)
            alloc = pd.Series(0.0, index=pnl)
            for acct in pnl:
                if acct in ("7000", "7010", "8000") or not ho.get(acct, 0.0):
                    continue
                drv = P.ALLOCATION.get(acct, ("revenue", ""))[0]
                alloc[acct] = ho[acct] * sh[drv].get(b, 0.0)
            rows.append((m, b, d, alloc))
        rows.append((m, P.HO, ho, -pd.Series({a: (ho[a] if a not in ("7000", "7010", "8000") else 0.0) for a in pnl})))
    out = []
    for m, b, d, alloc in rows:
        dd, aa = _is_from_activity(pd.DataFrame([d])), _is_from_activity(pd.DataFrame([alloc]))
        ib_rev, ib_cost = -d.get("4950", 0.0), -d.get("5450", 0.0)
        for k, *_ in IS_LINES:
            out.append(dict(month=str(m), branch_id=b, line=k, direct=float(dd[k].iloc[0]), allocated=float(aa[k].iloc[0])))
        for k, v in (("ib_rev", ib_rev), ("ib_cost", ib_cost)):
            out.append(dict(month=str(m), branch_id=b, line=k, direct=float(v), allocated=0.0))
    f = pd.DataFrame(out)
    f["total"] = f.direct + f.allocated
    return f


def branch_summary(bis, bs_branch):
    """Branch P&L by year incl. interbranch (contribution and operating profit after HO allocations)."""
    f = bis.copy()
    f["year"] = f.month.str[:4]
    p = f.pivot_table(index=["year", "branch_id"], columns="line", values="total", aggfunc="sum", fill_value=0.0)
    d = f.pivot_table(index=["year", "branch_id"], columns="line", values="direct", aggfunc="sum", fill_value=0.0)
    s = pd.DataFrame({"external_net_revenue": d["net_rev"], "interbranch_revenue": d["ib_rev"], "interbranch_cost": d["ib_cost"],
                      "gross_profit_incl_interbranch": d["gross_profit"] + d["ib_rev"] + d["ib_cost"],
                      "direct_operating_profit": d["ebit"] + d["ib_rev"] + d["ib_cost"],
                      "allocated_shared_costs": p["ebit"] - d["ebit"], "operating_profit_after_allocations": p["ebit"] + d["ib_rev"] + d["ib_cost"]})
    return s.round(2)


def branch_balances(gl):
    """Month-end working-capital balances by branch (AR, inventory, WIP, payables) from the branch dimension of the GL."""
    g = gl[gl.account.isin(["1100", "1110", "1120", "1200", "1210", "1220", "1250", "2000", "2010"])]
    a = g.groupby(["month", "branch_id", "account"]).amount.sum().unstack(fill_value=0.0)
    a = a.groupby(level="branch_id").cumsum()
    out = pd.DataFrame({"receivables": a.reindex(columns=["1100", "1110", "1120"], fill_value=0).sum(axis=1),
                        "inventory": a.reindex(columns=["1200", "1210", "1220"], fill_value=0).sum(axis=1), "wip": a.get("1250", 0.0),
                        "payables": -a.reindex(columns=["2000", "2010"], fill_value=0).sum(axis=1)})
    out["net_working_capital"] = out.receivables + out.inventory + out.wip - out.payables
    out = out.reset_index()
    out["month"] = out.month.astype(str)
    return out


def branch_cash_flow(bis, bb):
    """Approximate branch operating cash flow = branch EBITDA (direct, incl. interbranch) - change in branch net working capital."""
    d = bis[bis.line.isin(["ebitda", "ib_rev", "ib_cost"])].pivot_table(index=["month", "branch_id"], values="direct", aggfunc="sum")
    w = bb.set_index(["month", "branch_id"]).net_working_capital
    w = w.groupby(level="branch_id").diff().fillna(0.0)
    out = d.join(w.rename("d_nwc"), how="left").fillna(0.0)
    out["operating_cash_flow"] = out.direct - out.d_nwc
    return out.rename(columns={"direct": "ebitda_incl_interbranch"}).reset_index()


# ----------------------------------------------------------------------------------------------- reconciliations
def open_items(items, at):
    return items[(items.doc_date <= at) & (items.due_date > at)]


def subledger_reconciliation(gl, ar_items, ap_items):
    b = balances(gl)
    rows = []
    for m in MONTHS:
        at = m.end_time.normalize()
        for acct in ["1100", "1110", "1120"]:
            it = ar_items[ar_items.account == acct]
            if acct == "1100":
                sub = open_items(it, at).amount.sum()
            else:
                sub = it[(it.doc_date <= at) & ~(it.closed_date <= at)].amount.sum()
            rows.append({"month": str(m), "ledger": "AR", "control_account": acct, "gl_balance": round(b.at[m, acct], 2), "subledger": round(sub, 2)})
        for acct in ["2000", "2010"]:
            rows.append({"month": str(m), "ledger": "AP", "control_account": acct, "gl_balance": round(-b.at[m, acct], 2),
                         "subledger": round(open_items(ap_items[ap_items.account == acct], at).amount.sum(), 2)})
    r = pd.DataFrame(rows)
    r["difference"] = (r.gl_balance - r.subledger).round(2)
    return r


def wip_reconciliation(gl, T):
    """GL work in progress vs costs to date on open ROs from the operational records (parts, materials, sublet + applied labour)."""
    b = balances(gl)
    ro = T["repair_orders"]
    c = wip_components(T)
    rows = []
    for m in MONTHS:
        at = m.end_time.normalize()
        openro = set(ro[(ro.work_start_date <= at) & ~(ro.completion_date <= at)].ro_id) | set(ro[~(ro.completion_date <= at)].ro_id)
        mat = c[(c.date <= at) & c.ro_id.isin(openro)].cost.sum()
        lab = labour_wip_at(T, at).sum()
        n_open = int(((ro.inquiry_date <= at) & ~(ro.completion_date <= at)).sum())
        rows.append(dict(month=str(m), gl_wip=round(b.at[m, "1250"], 2), parts_materials_sublet=round(mat, 2), labour_applied=round(lab, 2),
                         operational_wip=round(mat + lab, 2), open_ros=n_open))
    r = pd.DataFrame(rows)
    r["difference"] = (r.gl_wip - r.operational_wip).round(2)
    return r


def aging(items, at=pd.Timestamp(END)):
    o = items[(items.doc_date <= at) & ~(items.closed_date <= at)].copy() if "closed_date" in items else open_items(items, at).copy()
    o["days_outstanding"] = (at - o.doc_date).dt.days
    o["bucket"] = pd.cut(o.days_outstanding, [-1, 30, 60, 90, 10_000], labels=["0-30", "31-60", "61-90", "90+"])
    return o


def inventory_valuation(T):
    mv = T["parts_inventory_movements"].assign(month=lambda x: x.movement_date.dt.to_period("M"))
    v = mv.pivot_table(index="month", columns="inventory_state", values="value_cad", aggfunc="sum", fill_value=0.0)
    v = v.reindex(pd.period_range(mv.month.min(), END, freq="M"), fill_value=0.0).cumsum().loc[MONTHS[0]:]
    out = pd.DataFrame({"stocked_parts": v.get("stock", 0).round(2), "special_order_parts_on_hand": v.get("job", 0).round(2), "materials": v.get("materials", 0).round(2)})
    out.index = out.index.astype(str)
    return out


def fixed_asset_register():
    from src.finance.ledger import opening_acc_dep
    dep = fixed_asset_schedule()
    acc = dep.groupby("asset_id").depreciation.sum()
    rows = []
    for a, d, ac, br, q, c, l in P.FIXED_ASSETS:
        a0 = opening_acc_dep(a) if pd.Timestamp(q) <= pd.Timestamp(P.OB_DATE) else 0.0
        rows.append({"asset_id": a, "description": d, "account": ac, "branch_id": br, "acquired": q, "cost": c, "useful_life_months": l,
                     "accumulated_depreciation_31dec2023": a0, "depreciation_2024_to_sep2026": round(acc.get(a, 0.0), 2),
                     "accumulated_depreciation_30sep2026": round(a0 + acc.get(a, 0.0), 2), "net_book_value_30sep2026": round(c - a0 - acc.get(a, 0.0), 2),
                     "data_status": "SIMULATED"})
    return pd.DataFrame(rows)


def build(L):
    gl = L["gl"]
    is_m = income_statement(gl)
    bs_m = balance_sheet(gl)
    cf_m = cash_flow(gl, is_m)
    bs_open = bs_m["2023-12"]
    bs_m = bs_m.drop(columns="2023-12")
    is_q, bs_q, cf_q = aggregate(is_m, bs_m, cf_m, "Q")
    is_y, bs_y, cf_y = aggregate(is_m, bs_m, cf_m, "Y")
    bis = branch_income_statements(gl, L["T"])
    bb = branch_balances(gl)
    return dict(is_m=is_m, bs_m=bs_m, cf_m=cf_m, bs_open=bs_open, is_q=is_q, bs_q=bs_q, cf_q=cf_q, is_y=is_y, bs_y=bs_y, cf_y=cf_y,
                cs_m=common_size(is_m), cs_y=common_size(is_y), tb=trial_balances(gl), direct=direct_cash_flow(gl),
                subledger=subledger_reconciliation(gl, L["ar_items"], L["ap_items"]), wip_rec=wip_reconciliation(gl, L["T"]), inv_val=inventory_valuation(L["T"]),
                far=fixed_asset_register(), bal=balances(gl), branch_is=bis, branch_summary=branch_summary(bis, bb), branch_bal=bb,
                branch_cf=branch_cash_flow(bis, bb))
