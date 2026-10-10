# Accounting policies and validation

SIMULATED FINANCIAL INFORMATION - synthetic accounts of a fictional auto care group.

## Policies

Chart of accounts and documented accounting policies for the SIMULATED accounts of the fictional Prairie Auto Care Group Ltd.
(one Alberta corporation, three branches plus a head office). Every figure is synthetic.

Revenue & work in progress (ASPE 3400, completed-contract basis - most repairs finish within days to a few weeks):
  * Repair revenue is recognised when the repair is complete, has passed quality control and the vehicle is delivered; the
    invoice is raised at delivery. Service lines: collision repair (incl. refinish), mechanical (incl. tires & diagnostics),
    detailing, glass, other services (PDR, paint protection, ADAS calibration, total-loss teardown and diagnostic fees).
  * Until then, costs of open (unbilled) jobs are carried at cost in WORK IN PROGRESS (1250): special-order and stocked parts
    when issued to the RO, paint & detailing materials when the paint / detail operation starts, sublet invoices when received,
    and technician labour at standard loaded cost (wage x 1.15) through a month-end accrual that is reversed on the 1st.
    No profit is recognised on WIP; WIP is released to cost of sales on delivery. (An IFRS 15 reporter would instead recognise
    revenue over time as work is performed; the demo documents the simpler ASPE completed-contract treatment.)
  * Insurer jobs are direct-billed: the customer pays the deductible (+ GST) at pickup; the insurer is invoiced for the
    approved repair value less the deductible (+ GST) and pays later (INSURER RECEIVABLE 1110). Short-pays on settlement are
    recorded as revenue adjustments (4900). Fleet accounts are invoiced on Net-30 (1120). Customer-pay jobs are paid at pickup;
    card and debit settle 1-2 days later (1100).
  * Warranty comebacks (lifetime workmanship warranty) are repaired at no charge: their parts and sublet go to 5400 and their
    labour stays in technician labour (5000).
  * Interbranch work (e.g. SE Concierge collision repaired at Central; paint protection done at SE for other branches) is
    charged at an internal transfer price: 4950 interbranch revenue (performing branch) and 5450 interbranch cost (selling
    branch). Both are ELIMINATED in the consolidated statements; external revenue is recognised once, by the selling branch.
Inventory: perpetual, moving-average cost. 1200 stocked parts; 1210 special-order parts received for specific open jobs
  (supplier returns credit the AP invoice); 1220 paint, refinish & detailing materials.

## Shared-cost allocation (management reporting only)

| Account | Driver | Explanation |
|---|---|---|
| 6010 | revenue | Group management & administration by share of external revenue |
| 6200 | revenue | Marketing by share of external revenue |
| 6300 | bays | Insurance by share of repair bays (exposure) |
| 6310 | revenue | Professional fees by share of external revenue |
| 6320 | headcount | Group software & IT by share of technician headcount |
| 6340 | headcount | Training & certification by share of technician headcount |
| 6900 | direct | HO-held IT hardware depreciation by technician headcount |

## Financial validation checks

|   check_no | check                                                                                                                                           | result   | detail                                                                                                                                                                                                       |
|-----------:|:------------------------------------------------------------------------------------------------------------------------------------------------|:---------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|          1 | General ledger balances: total debits = total credits (every journal entry)                                                                     | PASS     | 103,502 journal entries / 285,199 lines; debits $187,332,029.50 = credits $187,332,029.50; unbalanced entries: 0                                                                                             |
|          2 | Trial balances balance; card, insurer and fleet receivables and supplier/vendor payables equal their sub-ledgers                                | PASS     | 34 monthly trial balances; max sub-ledger difference by control account: 1100 $0.00, 1110 $0.00, 1120 $0.00, 2000 $0.00, 2010 $0.00                                                                          |
|          3 | Accounting equation: assets = liabilities + equity (every month-end, opening and forecast)                                                      | PASS     | Historical max |A-L-E| $0.00; opening $0.00; forecast (3 scenarios) $0.000000                                                                                                                                |
|          4 | Retained earnings: opening + net income - dividends = closing; current-year earnings = YTD net income                                           | PASS     | FY2024: 1,040,919 + 449,065 -179,000 = 1,310,984; FY2025: + 126,389 -50,000 = 1,387,373; YTD-2026 710,315                                                                                                    |
|          5 | Cash flow: ending cash = balance-sheet cash (monthly, quarterly, annual, forecast); direct method = indirect method                             | PASS     | Indirect-method ending cash ties every period; direct-method net change matches every month                                                                                                                  |
|          6 | Inventory: GL parts (stocked + special-order) and materials equal the inventory-movement records every month                                    | PASS     | Max difference $0.00; parts $126,399, materials $11,736 at 30-Sep-2026                                                                                                                                       |
|          7 | Work in progress: GL WIP equals costs to date on open (unbilled) ROs - parts, materials, sublet and applied labour                              | PASS     | 33 month-ends; WIP $115,919 on 218 open ROs at 30-Sep-2026                                                                                                                                                   |
|          8 | Revenue by line, adjustments and GST reconcile to invoices and payments; cost of sales reconciles to job costing and technician payroll         | PASS     | 12 lines x 33 months                                                                                                                                                                                         |
|          9 | Branches: branch + head-office P&Ls sum to the consolidated statements; interbranch revenue and cost eliminate exactly; allocations net to zero | PASS     | 33 months x 5 P&L lines; interbranch $541,310 eliminated                                                                                                                                                     |
|         10 | No balancing plugs                                                                                                                              | PASS     | No suspense/plug accounts; every line comes from a documented journal source; opening retained earnings is the documented residual of the explicit opening position; the forecast has no circular references |
|         11 | Forecasts remain integrated when assumptions change (Python and Excel)                                                                          | PASS     | 50 random assumption sets: max |A-L-E| or |cash difference| $0.000000; Excel recalculation (Base; Conservative; Custom): max |Excel - Python| $0.000000, Excel checks TRUE = True                            |
|         12 | All synthetic financial information is labelled                                                                                                 | PASS     | 40 financial CSV tables carry data_status; 46 workbook sheets carry the SIMULATED banner; 5 HTML/PDF reports labelled                                                                                        |

## Data validation checks

|   check_no | area          | check                                                                                                         |   violations |
|-----------:|:--------------|:--------------------------------------------------------------------------------------------------------------|-------------:|
|          1 | Integrity     | Primary keys unique in every table                                                                            |            0 |
|          2 | Integrity     | Foreign keys resolve (SQLite PRAGMA foreign_key_check)                                                        |            0 |
|          3 | Integrity     | Every RO's vehicle belongs to the RO's customer                                                               |            0 |
|          4 | Integrity     | Synthetic-data label on every row of every table                                                              |            0 |
|          5 | Workflow      | RO milestones in order (inquiry <= estimate <= approval <= parts <= start <= complete <= QC <= delivery)      |            0 |
|          6 | Workflow      | Delivered ROs have every milestone through delivery                                                           |            0 |
|          7 | Workflow      | Special-order parts complete before work starts (except supplement parts)                                     |            0 |
|          8 | Workflow      | No technician time booked after an RO is delivered or closed                                                  |            0 |
|          9 | Workflow      | Warranty comebacks follow a delivered original RO and are invoiced at $0                                      |            0 |
|         10 | Workflow      | Completed appointments link to an RO; no-shows / cancellations do not                                         |            0 |
|         11 | Claims        | Insurer-paid ROs have exactly one claim; other ROs none                                                       |            0 |
|         12 | Claims        | Claim approved value = estimate x insurer approval ratio                                                      |            0 |
|         13 | Invoices      | Invoice subtotals (all bill-to splits) = labour + parts + materials + sublet + fees - discount                |            0 |
|         14 | Invoices      | GST = 5% of every invoice subtotal; total = subtotal + GST                                                    |            0 |
|         15 | Invoices      | Insurer jobs: invoiced value = approved initial estimate + approved supplements                               |            0 |
|         16 | Invoices      | Invoiced parts = RO part lines (qty x price; x approval ratio on insurer jobs)                                |            0 |
|         17 | Invoices      | Billed hours by operation sum to RO billed labour hours                                                       |            0 |
|         18 | Payments      | Payments + short-pay adjustments never exceed the invoice; no payment before its invoice                      |            0 |
|         19 | Payments      | Customer and deductible portions paid at vehicle pickup (invoice date)                                        |            0 |
|         20 | Labour        | Job-assignment hours per RO = RO clocked labour hours                                                         |            0 |
|         21 | Labour        | Timesheet productive hours per technician-day = sum of job assignments                                        |            0 |
|         22 | Labour        | Productive hours <= attended hours (available + overtime); overtime only on attended days                     |            0 |
|         23 | Labour        | No job time on technicians' absence days or unscheduled days                                                  |            0 |
|         24 | Labour        | Assignments are at the RO's performing branch, by a technician of that branch whose role covers the operation |            0 |
|         25 | Labour        | Assignments only while the technician is employed                                                             |            0 |
|         26 | Inventory     | On-hand quantity never negative (stock, job-allocated and materials, every branch and part)                   |            0 |
|         27 | Inventory     | Parts issued to each RO (movements) = RO part lines installed (qty x cost)                                    |            0 |
|         28 | Inventory     | Paint & detailing materials issued = materials_issues by RO                                                   |            0 |
|         29 | Inventory     | Every received PO line has exactly its quantity received into inventory                                       |            0 |
|         30 | Inventory     | Special-order parts installed only after receipt                                                              |            0 |
|         31 | Inventory     | No special-order parts left in job-allocated stock for closed ROs                                             |            0 |
|         32 | Inventory     | Emergency orders are received the same day they are placed                                                    |            0 |
|         33 | Branches      | Interbranch transfer recorded for every delivered RO performed at another branch (and only those)             |            0 |
|         34 | Opex          | One operating-expense row per branch-month; no negative amounts                                               |            0 |
|         35 | External data | Real Calgary daily weather (ECCC) covers every day Jan-2024 to Sep-2026                                       |            0 |

