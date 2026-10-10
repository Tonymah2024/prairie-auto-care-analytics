"""Chart of accounts and documented accounting policies for the SIMULATED accounts of the fictional Prairie Auto Care Group Ltd.
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
"""
from __future__ import annotations

FIN_LABEL = "SIMULATED FINANCIAL INFORMATION - synthetic demonstration accounts of a fictional auto care group, not actual company records"

COA = [  # code, name, type, normal, statement line, cash-flow class
    ("1000", "Cash - operating account", "asset", "D", "Cash", "cash"),
    ("1100", "Card & debit processor receivable", "asset", "D", "Receivables", "op_wc"),
    ("1110", "Insurer receivables (direct billing)", "asset", "D", "Receivables", "op_wc"),
    ("1120", "Fleet & commercial account receivables", "asset", "D", "Receivables", "op_wc"),
    ("1200", "Parts inventory - stocked", "asset", "D", "Inventory", "op_wc"),
    ("1210", "Special-order parts received for open jobs", "asset", "D", "Inventory", "op_wc"),
    ("1220", "Paint, refinish & detailing materials", "asset", "D", "Inventory", "op_wc"),
    ("1250", "Work in progress - unbilled repair jobs (at cost)", "asset", "D", "Work in progress", "op_wc"),
    ("1300", "Prepaid expenses", "asset", "D", "Prepaid expenses", "op_wc"),
    ("1400", "GST input tax credits", "asset", "D", "Sales tax", "op_wc"),
    ("1500", "Leasehold improvements", "asset", "D", "Fixed assets", "ppe"),
    ("1510", "Shop equipment (paint booths, frame machines, lifts)", "asset", "D", "Fixed assets", "ppe"),
    ("1520", "Diagnostic, ADAS calibration & IT equipment", "asset", "D", "Fixed assets", "ppe"),
    ("1530", "Vehicles (shuttle & courtesy)", "asset", "D", "Fixed assets", "ppe"),
    ("1590", "Accumulated depreciation", "contra_asset", "C", "Accumulated depreciation", "accdep"),
    ("2000", "Accounts payable - parts & materials suppliers", "liability", "C", "Accounts payable", "op_wc"),
    ("2010", "Accounts payable - sublet & operating vendors", "liability", "C", "Accounts payable", "op_wc"),
    ("2100", "Accrued payroll", "liability", "C", "Accrued liabilities", "op_wc"),
    ("2300", "GST collected", "liability", "C", "Sales tax", "op_wc"),
    ("2400", "Income tax payable", "liability", "C", "Income tax payable", "op_wc"),
    ("2600", "Revolving operating line of credit", "liability", "C", "Revolver", "fin_rev"),
    ("2700", "Term loans", "liability", "C", "Term loans", "fin_term"),
    ("3000", "Share capital", "equity", "C", "Share capital", "equity"),
    ("3200", "Retained earnings", "equity", "C", "Retained earnings", "re"),
    ("3300", "Dividends declared", "equity", "D", "Retained earnings", "equity"),
    ("4000", "Collision repair revenue", "revenue", "C", "Revenue", "pnl"),
    ("4100", "Mechanical service revenue", "revenue", "C", "Revenue", "pnl"),
    ("4200", "Detailing revenue", "revenue", "C", "Revenue", "pnl"),
    ("4300", "Glass repair revenue", "revenue", "C", "Revenue", "pnl"),
    ("4400", "Other service revenue (PDR, paint protection, ADAS, fees)", "revenue", "C", "Revenue", "pnl"),
    ("4900", "Discounts, insurer short-pays & adjustments", "contra_revenue", "D", "Revenue adjustments", "pnl"),
    ("4950", "Interbranch service revenue (eliminated on consolidation)", "revenue", "C", "Interbranch", "pnl"),
    ("5000", "Technician labour (wages, overtime & burden)", "cogs", "D", "Cost of sales", "pnl"),
    ("5100", "Parts cost", "cogs", "D", "Cost of sales", "pnl"),
    ("5200", "Paint & materials cost", "cogs", "D", "Cost of sales", "pnl"),
    ("5300", "Subcontracted (sublet) repairs & towing", "cogs", "D", "Cost of sales", "pnl"),
    ("5400", "Warranty rework - parts & sublet", "cogs", "D", "Cost of sales", "pnl"),
    ("5450", "Interbranch sublet cost (eliminated on consolidation)", "cogs", "D", "Interbranch", "pnl"),
    ("5500", "Inventory adjustments & obsolescence", "cogs", "D", "Cost of sales", "pnl"),
    ("6000", "Wages - branch management, estimators, advisors & parts", "opex", "D", "Staff compensation", "pnl"),
    ("6010", "Salaries - group management & administration", "opex", "D", "Staff compensation", "pnl"),
    ("6100", "Rent", "opex", "D", "Occupancy", "pnl"),
    ("6105", "Common-area & property tax charges", "opex", "D", "Occupancy", "pnl"),
    ("6110", "Utilities", "opex", "D", "Occupancy", "pnl"),
    ("6200", "Marketing & advertising", "opex", "D", "Marketing", "pnl"),
    ("6300", "Insurance (garage liability & property)", "opex", "D", "General & administrative", "pnl"),
    ("6310", "Professional fees", "opex", "D", "General & administrative", "pnl"),
    ("6320", "Software & IT (shop management, estimating)", "opex", "D", "General & administrative", "pnl"),
    ("6330", "Collision network & OEM certification fees", "opex", "D", "General & administrative", "pnl"),
    ("6340", "Training & certification", "opex", "D", "General & administrative", "pnl"),
    ("6400", "Shop supplies & equipment maintenance", "opex", "D", "Shop operations", "pnl"),
    ("6410", "Courtesy vehicles, shuttle & concierge", "opex", "D", "Shop operations", "pnl"),
    ("6420", "Courier & waste disposal", "opex", "D", "Shop operations", "pnl"),
    ("6430", "Card processing fees", "opex", "D", "Shop operations", "pnl"),
    ("6900", "Depreciation", "opex", "D", "Depreciation", "pnl"),
    ("7000", "Interest - term loans", "other_exp", "D", "Interest", "pnl"),
    ("7010", "Interest - revolving line", "other_exp", "D", "Interest", "pnl"),
    ("8000", "Income tax expense", "tax", "D", "Income taxes", "pnl"),
]
ACCOUNTS = {c[0]: dict(zip(["code", "name", "type", "normal", "line", "cf"], c)) for c in COA}
PNL_TYPES = {"revenue", "contra_revenue", "cogs", "opex", "other_exp", "tax"}
REV_ACCT = {"Collision repair": "4000", "Mechanical service": "4100", "Detailing": "4200", "Glass repair": "4300", "Other services": "4400"}
INTERBRANCH = ("4950", "5450")
HO = "HO"

GST_RATE = 0.05
CARD_SETTLE_DAYS = {"Credit card": 2, "Debit": 1}
SUPPLIER_TERMS = {"SUP-01": 30, "SUP-02": 30, "SUP-03": 30, "SUP-04": 30, "SUP-05": 30, "SUP-06": 30, "SUP-07": 45, "SUP-08": 30}
VENDOR_TERMS_DAYS = 30
OPEX_PAY_DAY = 20
PAYROLL_FIRST_HALF = 0.50
LABOUR_BURDEN = 0.15
OT_PREMIUM = 1.5
TAX_SMALL_RATE, TAX_GENERAL_RATE, SMALL_BUSINESS_LIMIT = 0.11, 0.23, 500000.0   # Alberta CCPC: 9% + 2% on first $500K, 15% + 8% above
GST_TAXABLE_OPEX = {"6100", "6105", "6110", "6200", "6310", "6320", "6330", "6340", "6400", "6410", "6420"}
OPEX_MAP = [  # operating_expenses column, account (branch rows), account (HO row), vendor, kind (payroll | rent | prepaid | vendor)
    ("staff_wages_cad", "6000", "6010", None, "payroll"),
    ("rent_cad", "6100", "6100", "Landlord", "rent"), ("cam_property_tax_cad", "6105", "6105", "Landlord", "rent"),
    ("utilities_cad", "6110", "6110", "VEN-UTIL", "vendor"), ("shop_supplies_cad", "6400", "6400", "VEN-OPS", "vendor"),
    ("equipment_maintenance_cad", "6400", "6400", "VEN-OPS", "vendor"), ("software_it_cad", "6320", "6320", "VEN-OPS", "vendor"),
    ("network_certification_fees_cad", "6330", "6330", "VEN-OPS", "vendor"), ("courier_waste_cad", "6420", "6420", "VEN-OPS", "vendor"),
    ("courtesy_vehicles_concierge_cad", "6410", "6410", "VEN-OPS", "vendor"), ("card_processing_fees_cad", "6430", "6430", "VEN-PAY", "vendor"),
    ("marketing_cad", "6200", "6200", "VEN-OPS", "vendor"), ("insurance_cad", "6300", "6300", "Insurer", "prepaid"),
    ("professional_fees_cad", "6310", "6310", "VEN-OPS", "vendor"), ("training_certification_cad", "6340", "6340", "VEN-OPS", "vendor"),
]
FIXED_ASSETS = [  # asset_id, description, account, branch, acquired, cost, life (months)
    ("FA-001", "Central leasehold improvements (collision centre, ~10,000 sq ft)", "1500", "BR-CCC", "2016-03-01", 520000.0, 180),
    ("FA-002", "Central paint booths (2) & mixing room", "1510", "BR-CCC", "2017-06-01", 380000.0, 144),
    ("FA-003", "Central frame machine, lifts & welding equipment", "1510", "BR-CCC", "2018-04-01", 210000.0, 120),
    ("FA-004", "Central ADAS calibration & diagnostic equipment", "1520", "BR-CCC", "2022-03-01", 95000.0, 60),
    ("FA-005", "North leasehold improvements", "1500", "BR-NFS", "2019-01-15", 360000.0, 180),
    ("FA-006", "North paint booth & prep deck", "1510", "BR-NFS", "2019-03-01", 240000.0, 144),
    ("FA-007", "North lifts, alignment rack & tire equipment", "1510", "BR-NFS", "2019-03-01", 165000.0, 120),
    ("FA-008", "Shop IT, estimating & scanning hardware", "1520", "HO", "2021-09-01", 48000.0, 48),
    ("FA-009", "Customer shuttle van", "1530", "BR-CCC", "2022-05-01", 52000.0, 72),
    ("FA-010", "Central ADAS calibration rig upgrade", "1520", "BR-CCC", "2024-09-03", 68000.0, 60),
    ("FA-011", "SE Concierge leasehold fit-out (detail bays, PPF room)", "1500", "BR-SEC", "2025-03-03", 410000.0, 120),
    ("FA-012", "SE Concierge prep booth, lifts & tire equipment", "1510", "BR-SEC", "2025-04-01", 185000.0, 120),
    ("FA-013", "SE Concierge pickup & delivery vehicles (2)", "1530", "BR-SEC", "2025-04-15", 78000.0, 60),
    ("FA-014", "North second alignment rack", "1510", "BR-NFS", "2026-02-02", 42000.0, 96),
    ("FA-015", "Central paint booth refurbishment", "1510", "BR-CCC", "2026-05-04", 95000.0, 120),
]
OB_DATE = "2023-12-31"
LOANS = [  # loan_id, description, draw date, amount (balance at draw / at 31-Dec-2023), months remaining, spread over prime
    ("TL-1", "Term loan - equipment & leaseholds (existing)", OB_DATE, 420000.0, 48, 0.0200),
    ("TL-2", "Equipment loan - SE Concierge fit-out", "2025-03-03", 450000.0, 60, 0.0225),
]
PRIME_SPREAD_OVER_POLICY = 0.0220
REVOLVER = dict(limit=600000.0, spread=0.0100, min_cash=150000.0, target_cash=250000.0, repay_above=400000.0, step=5000.0,
                intramonth_floor=40000.0, intramonth_target=120000.0)
DIVIDEND = dict(payout=0.40, cash_floor=450000.0)   # year-end dividend: 40% of FY net income, only if cash stays above the floor and the revolver is nil
OPENING = dict(cash=420000.0, share_capital=200000.0, income_tax_2023=62000.0)

# shared (head-office) cost allocation to branches for management reporting - the GL itself keeps HO costs at HO
ALLOCATION = {  # account group: (driver, explanation)
    "6010": ("revenue", "Group management & administration by share of external revenue"),
    "6200": ("revenue", "Marketing by share of external revenue"),
    "6300": ("bays", "Insurance by share of repair bays (exposure)"),
    "6310": ("revenue", "Professional fees by share of external revenue"),
    "6320": ("headcount", "Group software & IT by share of technician headcount"),
    "6340": ("headcount", "Training & certification by share of technician headcount"),
    "6900": ("direct", "HO-held IT hardware depreciation by technician headcount"),
}
