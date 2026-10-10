# Prairie Auto Care Analytics — Repair Operations & Financial Intelligence Platform

**Developed by VisiVault Analytics Ltd. — Synthetic demonstration data. Not actual Ultimate Car Care Group records.**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://prairie-auto-care-bi.streamlit.app)

**▶ Live dashboard: <https://prairie-auto-care-bi.streamlit.app>**

> *Prairie Auto Care Group* is a **fictional** multi-location Calgary collision repair and car care business. Its business model (three Calgary locations with distinct
> roles, published hours, service menu, OEM-certified collision work, direct billing of insurers) is inspired by a public Calgary auto care group's website (retrieved
> Oct 2026). Every repair order, estimate, claim, technician, part, invoice, payment and financial figure is **synthetic**. Insurers, suppliers, customers and staff are
> fictional. Real public inputs: Calgary daily weather (ECCC), Alberta statutory holidays, Bank of Canada policy rate. No endorsement by or relationship with any real company is implied.

## What it contains

| Phase | Deliverable |
|---|---|
| 1 Dataset | Simulated Oct-2023 (warm-up) to Sep-2026: ~25,000 repair orders across 3 branches and 18+ interconnected tables (`data/synthetic/*.csv`, `data/prairie_auto_care_synthetic.db`) |
| 2 Job profitability | RO-level job costing (gross and fully loaded), estimate vs actual, unprofitable ROs, warranty rework, job calculator |
| 3 Technicians | Utilisation, efficiency, productivity (distinct, documented formulas), overtime, capacity, mix-adjusted fair comparison |
| 4 Workflow | Stage durations from inquiry to payment, bottlenecks, WIP, delayed repairs, model-estimated completion dates |
| 5 Parts | Stocked vs special-order parts, FIFO aging, turnover, stockouts / emergency orders, carrying cost, seasonal reorder points |
| 6 Insurance | Approval times, approved vs estimated, supplements, receivables ageing, payment days, admin workload (fictional insurers) |
| 7 Branches | Branch P&L with transfer pricing, eliminations and documented overhead allocation; branch cash flow and capacity |
| 8 Finance | Double-entry GL (~290k lines), monthly / quarterly / annual three statements, ratios, all reconciled |
| 9 Models | Revenue, RO volume & demand hours, cycle time, parts demand, technician capacity, cash collections - vs baselines, time-based validation |
| 10 Scenarios | Integrated 12-month forecast with capacity-constrained revenue; Excel model with live formulas |
| 11 Dashboard | 15-page Streamlit + Plotly app (`dashboard/app.py`) |
| 12-13 Reports | Management report, business-development proposal, 90-day pilot plan, demo guide (`outputs/reports/*.pdf`) |

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py            # rebuilds everything (~4 min); stops if any validation check fails
streamlit run dashboard/app.py
python -m pytest                  # tests
```

## Validation

* 35 data-validation checks (keys, workflow order, invoices = components, GST, labour hours = timesheets = assignments, inventory never negative,
  parts issued = RO part lines, interbranch transfers...) - all zero violations.
* 12 financial checks: balanced GL and trial balances; AR / AP sub-ledgers; A = L + E every month; retained-earnings roll-forward; cash-flow ties (direct = indirect);
  inventory and **WIP equal the operational records**; revenue / cost of sales reconcile to invoices, job costs and payroll; **branch P&Ls sum to the consolidated
  statements with interbranch eliminated**; no plugs; forecast integrity under 50 random scenarios and an Excel recalculation; labelling.
* Model performance on synthetic data does **not** establish real-world prediction accuracy.

Details: `docs/accounting_policies_and_validation.md`, `docs/model_evaluation.md`, `docs/data_dictionary.md`. Deployment: `docs/deployment_streamlit_cloud.md`.
