"""Financial ratio analysis of the SIMULATED accounts (TTM flows; month-end or 13-point average balances)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.finance import policy as P

DEFINITIONS = [  # key, name, group, formula, meaning, unit, higher_is_better
    ("gross_margin", "Gross profit margin", "Profitability", "Gross profit / total net revenue", "Pricing, parts margin and technician productivity after all job costs.", "%", True),
    ("operating_margin", "Operating margin", "Profitability", "Operating income (EBIT) / total net revenue", "Profit from operations after overheads and depreciation.", "%", True),
    ("ebitda_margin", "EBITDA margin", "Profitability", "EBITDA / total net revenue", "Operating cash earnings before depreciation, interest and tax.", "%", True),
    ("net_margin", "Net profit margin", "Profitability", "Net income / total net revenue", "Bottom-line profit per dollar of revenue.", "%", True),
    ("roe", "Return on equity", "Profitability", "TTM net income / average equity", "Return earned on the owners' capital.", "%", True),
    ("current_ratio", "Current ratio", "Liquidity", "Current assets / current liabilities", "Short-term solvency.", "x", True),
    ("quick_ratio", "Quick ratio", "Liquidity", "(Cash + receivables) / current liabilities", "Liquidity without relying on parts inventory or WIP.", "x", True),
    ("working_capital", "Working capital", "Liquidity", "Current assets - current liabilities", "Net short-term resources.", "$", True),
    ("dso", "Days sales outstanding", "Efficiency", "Average receivables / (TTM net revenue x 1.05) x 365", "Days to collect, all payers (insurers dominate).", "days", False),
    ("dso_insurer", "Insurer days outstanding", "Efficiency", "Average insurer receivables / (TTM insurer-billed revenue x 1.05) x 365",
     "Days from invoicing an insurer to receiving its EFT.", "days", False),
    ("inventory_turnover", "Inventory turnover", "Efficiency", "TTM parts & materials cost / average parts & materials inventory", "How often parts stock turns each year.", "x", True),
    ("dio", "Days inventory outstanding", "Efficiency", "365 / inventory turnover", "Days of parts & materials on hand.", "days", False),
    ("wip_days", "Days in work in progress", "Efficiency", "Average WIP / TTM cost of sales x 365", "Days of job cost tied up in unbilled repairs (cycle-time cost).", "days", False),
    ("dpo", "Days payables outstanding", "Efficiency", "Average supplier & vendor payables / TTM purchases-based cost (parts, materials, sublet) x 365", "Days of supplier credit used.", "days", True),
    ("ccc", "Cash conversion cycle", "Efficiency", "DIO + WIP days + DSO - DPO", "Days between paying for parts and collecting from the payer.", "days", False),
    ("asset_turnover", "Asset turnover", "Efficiency", "TTM net revenue / average total assets", "Revenue per dollar of assets.", "x", True),
    ("debt_to_equity", "Debt-to-equity", "Solvency", "(Revolver + term loans) / equity", "Reliance on borrowed money.", "x", False),
    ("interest_coverage", "Interest coverage", "Solvency", "TTM EBIT / TTM interest", "Headroom to service interest.", "x", True),
]
DEF = {d[0]: d for d in DEFINITIONS}
ACTIONS = {
    "gross_margin": "Raise technician efficiency on flat-rate work, review parts pricing on customer-pay jobs, cut warranty comebacks.",
    "operating_margin": "Bring SE Concierge to break-even; hold overhead flat as volume grows.",
    "ebitda_margin": "Same levers as operating margin; staffing to demand by branch and season.",
    "net_margin": "Combine margin and overhead actions; keep borrowing low.",
    "roe": "Profit growth with a disciplined dividend policy.",
    "current_ratio": "Comfortable; monitor as insurer receivables grow with collision volume.",
    "quick_ratio": "Strong; receivables are mostly insurers (low credit risk, slow cash).",
    "working_capital": "Size working capital to collision WIP and insurer payment cycles.",
    "dso": "Submit insurer invoices with complete photo/supplement files on delivery day; chase >30-day items weekly.",
    "dso_insurer": "Track by insurer; escalate items beyond agreed terms; electronic invoicing where available.",
    "inventory_turnover": "Seasonal reorder points (tires), smaller stocked range at SE, return slow special-order parts promptly.",
    "dio": "Cut cover on slow stocked SKUs.",
    "wip_days": "Shorten parts waiting and supplement approval times - faster delivery bills sooner.",
    "dpo": "Use full supplier terms; consolidate payments.",
    "ccc": "Lower WIP days and insurer DSO.",
    "asset_turnover": "Lift SE Concierge utilisation.",
    "debt_to_equity": "Low; equipment loan amortising.",
    "interest_coverage": "Comfortable.",
}


def compute(is_m, bs_m, bs_open, insurer_rev_m):
    bs = pd.concat([bs_open.rename("2023-12"), bs_m], axis=1)
    cols = list(is_m.columns)
    out = {}
    for i in range(11, len(cols)):
        w = cols[i - 11:i + 1]
        bw = ["2023-12" if i == 11 else cols[i - 12]] + w
        f = is_m[w].sum(axis=1)
        b = bs[cols[i]]
        avg = bs[bw].mean(axis=1)
        nr = f["net_rev"]
        inv_avg = avg["inventory"] + avg["materials"]
        pm = -(f["parts"] + f["materials"] + f["inv_adj"] + f["warranty"])
        turn = pm / inv_avg
        ar_avg = avg["ar_insurer"] + avg["ar_other"]
        dso = ar_avg / (nr * (1 + P.GST_RATE)) * 365
        ins_rev = insurer_rev_m.reindex(w).fillna(0).sum()
        dso_i = avg["ar_insurer"] / (ins_rev * (1 + P.GST_RATE)) * 365 if ins_rev else np.nan
        wip_days = avg["wip"] / -f["cogs"] * 365
        dpo = avg["ap"] / -(f["parts"] + f["materials"] + f["sublet"] + f["warranty"]) * 365
        debt = b["revolver"] + b["term_current"] + b["term_lt"]
        out[cols[i]] = {"gross_margin": f["gross_profit"] / nr * 100, "operating_margin": f["ebit"] / nr * 100, "ebitda_margin": f["ebitda"] / nr * 100,
                        "net_margin": f["net_income"] / nr * 100, "roe": f["net_income"] / avg["total_equity"] * 100,
                        "current_ratio": b["current_assets"] / b["current_liabilities"], "quick_ratio": (b["cash"] + b["ar_insurer"] + b["ar_other"]) / b["current_liabilities"],
                        "working_capital": b["current_assets"] - b["current_liabilities"], "dso": dso, "dso_insurer": dso_i, "inventory_turnover": turn, "dio": 365 / turn,
                        "wip_days": wip_days, "dpo": dpo, "ccc": 365 / turn + wip_days + dso - dpo, "asset_turnover": nr / avg["total_assets"],
                        "debt_to_equity": debt / b["total_equity"], "interest_coverage": f["ebit"] / -f["interest"] if f["interest"] else np.nan}
    return pd.DataFrame(out).loc[[d[0] for d in DEFINITIONS]]


def annual_table(r):
    t = r[["2024-12", "2025-12", "2026-09"]].copy()
    t.columns = ["FY2024", "FY2025", "TTM Sep-2026"]
    t["change_vs_FY2025"] = t["TTM Sep-2026"] - t["FY2025"]
    meta = pd.DataFrame([d[1:] for d in DEFINITIONS], index=[d[0] for d in DEFINITIONS], columns=["ratio", "group", "formula", "meaning", "unit", "higher_is_better"])
    t = meta.join(t)
    t["direction"] = np.where(t.change_vs_FY2025.abs() < 1e-9, "flat", np.where((t.change_vs_FY2025 > 0) == t.higher_is_better, "improved", "deteriorated"))
    t["management_action"] = t.index.map(ACTIONS)
    return t


def ar_aging_monthly(ar_items, months):
    """Insurer & fleet receivables ageing at each month end (days since invoice)."""
    rows = []
    it = ar_items[ar_items.account.isin(["1110", "1120"])]
    for m in months:
        at = m.end_time.normalize()
        o = it[(it.doc_date <= at) & ~(it.closed_date <= at)]
        days = (at - o.doc_date).dt.days
        b = pd.cut(days, [-1, 30, 60, 90, 10_000], labels=["0-30", "31-60", "61-90", "90+"])
        g = o.groupby([o.account, b], observed=False).amount.sum()
        for (acct, bucket), v in g.items():
            rows.append(dict(month=str(m), account=acct, bucket=str(bucket), amount=round(v, 2)))
    return pd.DataFrame(rows)
