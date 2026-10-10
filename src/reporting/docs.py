"""Generated documentation: data dictionary, model evaluation, accounting policies & validation results, deployment notes."""
from __future__ import annotations

import json

import pandas as pd

from src.config import DOCS, SYNTH, TABLES
from src.engineering.load_db import KEYS
from src.finance import policy as P

DESC = {  # table descriptions
    "branches": "The three fictional branches (role, opening date, hours, repair bays).", "customers": "Individual and fleet customers (fictional).",
    "vehicles": "Customer vehicles: make, category, model year, powertrain, ADAS equipment.", "repair_orders": "One row per repair order (RO): workflow milestones, payer, hours, status.",
    "repair_estimates": "Initial estimates and supplements with approved values.", "insurers": "Fictional insurers and their category (DRP, non-DRP, fleet / self-insured).",
    "insurance_claims": "One claim per insurer-paid RO: type, deductible, estimate vs approved, supplements, admin workload.",
    "technicians": "Technician profiles: branch, role, op groups, wage, efficiency and rework factors (synthetic).",
    "technician_timesheets": "Daily schedule, absence, training, overtime, attended and productive hours per technician.",
    "job_assignments": "Clocked technician time per RO, day and operation, with loaded labour cost.", "parts_catalogue": "Stocked parts, special-order parts and materials.",
    "ro_part_lines": "Parts installed on each RO (stocked or special order) with cost and price.",
    "parts_inventory_movements": "Perpetual inventory: opening, receipts, issues to ROs, supplier returns, adjustments (stock / job / materials).",
    "suppliers": "Fictional parts & materials suppliers.", "supplier_purchase_orders": "PO lines: special order, stock replenishment, emergency, materials.",
    "stock_policy_current": "Current (flat, non-seasonal) reorder point and order-up-to level per branch-SKU.", "sublet_lines": "Sublet and towing costs per RO.",
    "sublet_vendors": "Fictional sublet & operating vendors.", "service_appointments": "Bookings, appointment dates and outcomes (completed, no-show, cancelled).",
    "customer_invoices": "Invoices raised at delivery, split by bill-to (customer / deductible, insurer, fleet).", "payments": "Payments and insurer short-pay adjustments.",
    "interbranch_transfers": "Internal transfer price for work performed by another branch.", "materials_issues": "Paint & detailing materials issued to ROs.",
    "operating_expenses": "Monthly operating expenses by branch and head office.",
}


def data_dictionary():
    lines = ["# Data dictionary - Prairie Auto Care Analytics (SYNTHETIC DATA)", "",
             "Synthetic demonstration data. Not actual Ultimate Car Care Group records. All entities are fictional. Dates are ISO (YYYY-MM-DD); amounts in CAD.", "",
             "Records dated Oct-Dec 2023 (`pre_period = 1` on repair orders) are a warm-up quarter used only to build the opening balance sheet.", "",
             "The general ledger, chart of accounts, trial balances and fixed-asset register are produced by the finance step "
             "(`fin_*` tables in the SQLite database and `outputs/tables/fin_*.csv`).", ""]
    for t, (pk, fks) in KEYS.items():
        df = pd.read_csv(SYNTH / f"{t}.csv", nrows=2000, low_memory=False)
        n = sum(1 for _ in open(SYNTH / f"{t}.csv")) - 1
        lines += [f"## {t}", "", f"{DESC.get(t, '')} Rows: {n:,}. Primary key: `{pk or '-'}`." + (" Foreign keys: " + ", ".join(f"`{c}` -> {r}" for c, r in fks.items()) if fks else ""), "",
                  "| Column | Type | Example |", "|---|---|---|"]
        for c in df.columns:
            ex = df[c].dropna().iloc[0] if df[c].notna().any() else ""
            lines.append(f"| {c} | {df[c].dtype} | {str(ex)[:60]} |")
        lines.append("")
    lines += ["## Chart of accounts", "", "| Code | Name | Type | Statement line |", "|---|---|---|---|"] + [f"| {c[0]} | {c[1]} | {c[2]} | {c[4]} |" for c in P.COA]
    (DOCS / "data_dictionary.md").write_text("\n".join(lines) + "\n")


def model_doc():
    r = json.loads((TABLES / "model_results.json").read_text())
    ev = pd.read_csv(TABLES / "forecast_model_comparison.csv")
    ct = pd.read_csv(TABLES / "cycle_time_model_evaluation.csv")
    co = pd.read_csv(TABLES / "collections_model_evaluation.csv")
    hold = ev[ev.holdout == 1].pivot_table(index="target", columns="method", values="WAPE").round(3)
    lines = ["# Predictive models - evaluation", "", f"**{r['disclaimer']}**", "",
             "Validation is time-based: every origin trains only on months up to the origin; the last origin is the holdout (final 6 months). "
             "Model choice = lowest average of holdout WAPE and mean WAPE across origins, subject to a reasonableness band (12-month total within -15% / +25% of the trailing 12 months).", "",
             "## 1-2, 4-5. Monthly series - holdout WAPE by method", "", hold.to_markdown(), "", "Chosen models:", ""]
    lines += [f"- {k}: {v}" for k, v in r["chosen_models"].items()]
    lines += ["", "## 3. Repair cycle-time prediction (collision, approval -> delivery days; test = approvals in 2026)", "", ct.drop(columns=["data_status"], errors="ignore").round(3).to_markdown(index=False),
              "", "Features are known at approval time only (estimate hours and value, special-order lines, luxury / aftermarket suppliers, ADAS, towed, payer, vehicle category, branch, "
              "month, open collision jobs at the branch). Supplements and backorders are NOT used as inputs (unknown at approval).", "",
              "## 6. Expected cash collections (insurer & fleet receivables collected within 30 days)", "", co.round(3).to_markdown(index=False), ""]
    (DOCS / "model_evaluation.md").write_text("\n".join(lines) + "\n")


def accounting_doc():
    ch = pd.read_csv(TABLES / "fin_validation_checks.csv")
    dq = pd.read_csv(TABLES / "data_validation_checks.csv")
    lines = ["# Accounting policies and validation", "", "SIMULATED FINANCIAL INFORMATION - synthetic accounts of a fictional auto care group.", "", "## Policies", "",
             P.__doc__.strip(), "", "## Shared-cost allocation (management reporting only)", "", "| Account | Driver | Explanation |", "|---|---|---|"]
    lines += [f"| {k} | {v[0]} | {v[1]} |" for k, v in P.ALLOCATION.items()]
    lines += ["", "## Financial validation checks", "", ch[["check_no", "check", "result", "detail"]].to_markdown(index=False), "",
              "## Data validation checks", "", dq[["check_no", "area", "check", "violations"]].to_markdown(index=False), ""]
    (DOCS / "accounting_policies_and_validation.md").write_text("\n".join(lines) + "\n")


def deployment_doc():
    (DOCS / "deployment_streamlit_cloud.md").write_text("""# Deploying to Streamlit Community Cloud

1. Push the repository to GitHub (the generated `data/synthetic`, `data/*.db` and `outputs/` folders must be committed - the app reads them; it does not rebuild the data).
2. On https://share.streamlit.io choose **New app**, select the repository and branch, main file `dashboard/app.py`, Python 3.11.
3. Requirements are read from `requirements.txt`; the theme from `.streamlit/config.toml`.
4. After the first start, open each of the 15 pages once and confirm there are no errors; only then publish the URL.
5. To refresh the data: run `python run_pipeline.py` locally and commit the regenerated outputs.

Local run: `pip install -r requirements.txt && streamlit run dashboard/app.py`.
PDF rendering in the pipeline uses a local Chrome / Edge; Excel verification of the integrated model uses Microsoft Excel on macOS when available (otherwise skipped).
""")


def run():
    data_dictionary()
    model_doc()
    accounting_doc()
    deployment_doc()


if __name__ == "__main__":
    run()
