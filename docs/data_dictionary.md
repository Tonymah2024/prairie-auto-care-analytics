# Data dictionary - Prairie Auto Care Analytics (SYNTHETIC DATA)

Synthetic demonstration data. Not actual Ultimate Car Care Group records. All entities are fictional. Dates are ISO (YYYY-MM-DD); amounts in CAD.

Records dated Oct-Dec 2023 (`pre_period = 1` on repair orders) are a warm-up quarter used only to build the opening balance sheet.

The general ledger, chart of accounts, trial balances and fixed-asset register are produced by the finance step (`fin_*` tables in the SQLite database and `outputs/tables/fin_*.csv`).

## branches

The three fictional branches (role, opening date, hours, repair bays). Rows: 3. Primary key: `branch_id`.

| Column | Type | Example |
|---|---|---|
| branch_id | object | BR-SEC |
| branch_name | object | Southeast Concierge |
| role | object | Newest location: detailing, paint protection, PDR, light col |
| opened_date | object | 2025-05-01 |
| saturday_hours | float64 | 3.0 |
| repair_bays | int64 | 8 |
| weekday_hours | object | 08:00-17:00 |
| saturday_open | object | 10:00-13:00 |
| data_status | object | SYNTHETIC |

## insurers

Fictional insurers and their category (DRP, non-DRP, fleet / self-insured). Rows: 10. Primary key: `insurer_id`.

| Column | Type | Example |
|---|---|---|
| insurer_id | object | INS-01 |
| insurer_name | object | Chinook Mutual Insurance (fictional) |
| insurer_category | object | DRP insurer (direct repair program) |
| payment_days_mean | int64 | 18 |
| payment_days_sd | int64 | 6 |
| approval_days_mean | float64 | 0.6 |
| approval_ratio_mean | float64 | 0.985 |
| share_of_claims | float64 | 0.17 |
| data_status | object | SYNTHETIC |

## suppliers

Fictional parts & materials suppliers. Rows: 8. Primary key: `supplier_id`.

| Column | Type | Example |
|---|---|---|
| supplier_id | object | SUP-01 |
| supplier_name | object | Bow City OEM Parts Network (fictional) |
| supplier_type | object | OEM dealer parts |
| payment_terms_days | int64 | 30 |
| lead_time_mean_days | float64 | 1.8 |
| lead_time_sd_days | float64 | 1.0 |
| on_time_target | float64 | 0.88 |
| emergency_premium | float64 | 0.12 |
| data_status | object | SYNTHETIC |

## sublet_vendors

Fictional sublet & operating vendors. Rows: 6. Primary key: `vendor_id`.

| Column | Type | Example |
|---|---|---|
| vendor_id | object | VEN-TOW |
| vendor_name | object | Fictional towing partner |
| vendor_type | object | Towing & storage |
| data_status | object | SYNTHETIC |

## customers

Individual and fleet customers (fictional). Rows: 15,632. Primary key: `customer_id`. Foreign keys: `home_branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| customer_id | object | CUS-000001 |
| customer_type | object | Fleet account |
| account_name | object | Bowness Plumbing & Heating (fictional) |
| home_branch_id | object | BR-NFS |
| calgary_quadrant | object | NE |
| acquisition_channel | object | Commercial account |
| first_visit_date | object | 2023-10-01 |
| fleet_discount_pct | float64 | 7.0 |
| data_status | object | SYNTHETIC |

## vehicles

Customer vehicles: make, category, model year, powertrain, ADAS equipment. Rows: 17,052. Primary key: `vehicle_id`. Foreign keys: `customer_id` -> customers.customer_id

| Column | Type | Example |
|---|---|---|
| vehicle_id | object | VEH-000001 |
| customer_id | object | CUS-000001 |
| make | object | Toyota |
| vehicle_category | object | Compact & sedan |
| model_year | int64 | 2025 |
| powertrain | object | Gasoline / diesel |
| adas_equipped | int64 | 1 |
| data_status | object | SYNTHETIC |

## technicians

Technician profiles: branch, role, op groups, wage, efficiency and rework factors (synthetic). Rows: 42. Primary key: `tech_id`. Foreign keys: `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| tech_id | object | TEC-001 |
| branch_id | object | BR-CCC |
| role | object | Collision technician (Red Seal) |
| op_groups | object | BODY|PDR |
| hire_date | object | 2015-11-06 |
| termination_date | object | 2024-06-28 |
| base_wage_2024 | float64 | 43.83 |
| efficiency_factor | float64 | 1.3708440075043082 |
| rework_factor | float64 | 0.6364513112877314 |
| red_seal | int64 | 1 |
| data_status | object | SYNTHETIC |

## parts_catalogue

Stocked parts, special-order parts and materials. Rows: 446. Primary key: `part_id`. Foreign keys: `default_supplier_id` -> suppliers.supplier_id

| Column | Type | Example |
|---|---|---|
| part_id | object | PRT-00001 |
| part_number | object | STK-00001 |
| description | object | Clips & fasteners kit |
| part_category | object | clips |
| part_type | object | Stocked |
| oem_or_aftermarket | object | Aftermarket / supplier brand |
| make | object | Toyota |
| standard_unit_cost_2024 | float64 | 18.0 |
| unit_list_price_2024 | float64 | 39.6 |
| default_supplier_id | object | SUP-02 |
| stocked_at | object | BR-CCC|BR-NFS|BR-SEC |
| data_status | object | SYNTHETIC |

## repair_orders

One row per repair order (RO): workflow milestones, payer, hours, status. Rows: 26,949. Primary key: `ro_id`. Foreign keys: `branch_id` -> branches.branch_id, `performing_branch_id` -> branches.branch_id, `customer_id` -> customers.customer_id, `vehicle_id` -> vehicles.vehicle_id, `insurer_id` -> insurers.insurer_id, `warranty_of_ro` -> repair_orders.ro_id

| Column | Type | Example |
|---|---|---|
| ro_id | object | RO-000001 |
| branch_id | object | BR-CCC |
| performing_branch_id | object | BR-CCC |
| interbranch | int64 | 0 |
| customer_id | object | CUS-000023 |
| vehicle_id | object | VEH-000201 |
| service_type | object | COL_MIN |
| service_name | object | Collision repair - minor (bumper, scuffs, lamps) |
| service_line | object | Collision repair |
| payer_type | object | Insurance |
| insurer_id | object | INS-01 |
| drp_insurer | int64 | 1 |
| channel | object | Online booking |
| towed_in | int64 | 0 |
| hail_related | int64 | 0 |
| warranty_of_ro | float64 |  |
| inquiry_date | object | 2023-10-02 |
| estimate_date | object | 2023-10-05 |
| approval_date | object | 2023-10-05 |
| parts_ordered_date | object | 2023-10-06 |
| parts_received_date | object | 2023-10-19 |
| vehicle_in_date | object | 2023-10-19 |
| work_start_date | object | 2023-10-19 |
| work_complete_date | object | 2023-10-20 |
| qc_date | object | 2023-10-23 |
| original_promised_date | object | 2023-10-24 |
| promised_date | object | 2023-10-24 |
| delivered_date | object | 2023-10-24 |
| closed_date | object | 2023-10-24 |
| status | object | Delivered |
| supplement_count | int64 | 0 |
| est_labour_hours | float64 | 4.7 |
| billed_labour_hours | float64 | 4.7 |
| clocked_labour_hours | float64 | 4.48 |
| internal_rework_hours | float64 | 0.0 |
| billed_body_hours | float64 | 2.6 |
| billed_paint_hours | float64 | 2.1 |
| billed_mech_hours | float64 | 0.0 |
| billed_calib_hours | float64 | 0.0 |
| billed_glass_hours | float64 | 0.0 |
| billed_detail_hours | float64 | 0.0 |
| billed_ppf_hours | float64 | 0.0 |
| billed_pdr_hours | float64 | 0.0 |
| csat_score | float64 | 5.0 |
| est_total_cad | float64 | 2264.59 |
| est_parts_cost_cad | float64 | 1135.73 |
| approval_ratio | float64 | 1.0 |
| pre_period | int64 | 1 |
| data_status | object | SYNTHETIC |

## repair_estimates

Initial estimates and supplements with approved values. Rows: 27,718. Primary key: `estimate_id`. Foreign keys: `ro_id` -> repair_orders.ro_id

| Column | Type | Example |
|---|---|---|
| estimate_id | object | EST-000001 |
| ro_id | object | RO-000001 |
| estimate_type | object | Initial |
| estimate_date | object | 2023-10-05 |
| labour_hours | float64 | 4.7 |
| labour_cad | float64 | 528.84 |
| parts_cad | float64 | 1632.85 |
| paint_materials_cad | float64 | 102.9 |
| sublet_cad | float64 | 0.0 |
| total_estimate_cad | float64 | 2264.59 |
| approved_by | object | Insurer |
| approval_date | object | 2023-10-05 |
| approval_status | object | Approved |
| approved_total_cad | float64 | 2264.59 |
| est_parts_cost_cad | float64 | 1135.73 |
| data_status | object | SYNTHETIC |

## insurance_claims

One claim per insurer-paid RO: type, deductible, estimate vs approved, supplements, admin workload. Rows: 5,599. Primary key: `claim_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `insurer_id` -> insurers.insurer_id

| Column | Type | Example |
|---|---|---|
| claim_id | object | CLM-000001 |
| ro_id | object | RO-000001 |
| insurer_id | object | INS-01 |
| claim_type | object | Collision (at fault) |
| claim_number | object | FICT-38709159 |
| loss_date | object | 2023-10-01 |
| submitted_date | object | 2023-10-05 |
| approval_date | object | 2023-10-05 |
| deductible_cad | float64 | 1000.0 |
| estimate_value_cad | float64 | 2264.59 |
| approved_value_cad | float64 | 2264.59 |
| supplement_count | int64 | 0 |
| supplement_estimate_cad | float64 | 0.0 |
| supplement_approved_cad | float64 | 0.0 |
| outcome | object | Approved |
| insurer_contacts | int64 | 3 |
| admin_hours | float64 | 1.25 |
| data_status | object | SYNTHETIC |

## technician_timesheets

Daily schedule, absence, training, overtime, attended and productive hours per technician. Rows: 25,259. Primary key: `timesheet_id`. Foreign keys: `tech_id` -> technicians.tech_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| timesheet_id | object | TS-0000001 |
| tech_id | object | TEC-001 |
| branch_id | object | BR-CCC |
| work_date | object | 2023-10-02 |
| scheduled_hours | float64 | 8.0 |
| absence_type | object | Sick |
| paid_absence_hours | float64 | 0.0 |
| training_hours | float64 | 0.0 |
| available_hours | float64 | 8.0 |
| overtime_hours | float64 | 0.0 |
| attended_hours | float64 | 8.0 |
| productive_hours | float64 | 0.0 |
| hourly_wage_cad | float64 | 42.55 |
| data_status | object | SYNTHETIC |

## job_assignments

Clocked technician time per RO, day and operation, with loaded labour cost. Rows: 49,621. Primary key: `assignment_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `tech_id` -> technicians.tech_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| assignment_id | object | ASG-0000001 |
| ro_id | object | RO-000001 |
| tech_id | object | TEC-001 |
| branch_id | object | BR-CCC |
| work_date | object | 2023-10-19 |
| operation | object | BODY |
| clocked_hours | float64 | 0.58 |
| internal_rework | int64 | 0 |
| labour_cost_cad | float64 | 28.38 |
| data_status | object | SYNTHETIC |

## supplier_purchase_orders

PO lines: special order, stock replenishment, emergency, materials. Rows: 37,413. Primary key: `po_line_id`. Foreign keys: `supplier_id` -> suppliers.supplier_id, `branch_id` -> branches.branch_id, `part_id` -> parts_catalogue.part_id, `ro_id` -> repair_orders.ro_id

| Column | Type | Example |
|---|---|---|
| po_line_id | object | POL-0000001 |
| supplier_id | object | SUP-08 |
| branch_id | object | BR-CCC |
| part_id | object | PRT-00359 |
| ro_id | object | RO-000001 |
| po_type | object | Special order |
| order_date | object | 2023-10-06 |
| promised_date | object | 2023-10-18 |
| received_date | object | 2023-10-18 |
| qty_ordered | float64 | 1.0 |
| unit_cost_cad | float64 | 147.04 |
| backorder | int64 | 0 |
| returned_date | object | 2023-10-10 |
| replacement_for_return | int64 | 0 |
| supplement | int64 | 0 |
| emergency | int64 | 0 |
| data_status | object | SYNTHETIC |

## ro_part_lines

Parts installed on each RO (stocked or special order) with cost and price. Rows: 54,566. Primary key: `ro_line_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `part_id` -> parts_catalogue.part_id, `po_line_id` -> supplier_purchase_orders.po_line_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| ro_line_id | object | ROL-0000001 |
| ro_id | object | RO-000001 |
| part_id | object | PRT-00359 |
| source | object | Special order |
| qty | int64 | 1 |
| unit_cost_cad | float64 | 147.04 |
| unit_price_cad | float64 | 199.88 |
| supplement | int64 | 0 |
| issue_date | object | 2023-10-19 |
| po_line_id | object | POL-0000001 |
| branch_id | object | BR-CCC |
| data_status | object | SYNTHETIC |

## parts_inventory_movements

Perpetual inventory: opening, receipts, issues to ROs, supplier returns, adjustments (stock / job / materials). Rows: 99,868. Primary key: `movement_id`. Foreign keys: `branch_id` -> branches.branch_id, `part_id` -> parts_catalogue.part_id, `ro_id` -> repair_orders.ro_id, `po_line_id` -> supplier_purchase_orders.po_line_id

| Column | Type | Example |
|---|---|---|
| movement_id | object | MOV-0000001 |
| movement_date | object | 2023-09-30 |
| branch_id | object | BR-CCC |
| part_id | object | PRT-00001 |
| movement_type | object | OPENING_BALANCE |
| inventory_state | object | stock |
| quantity | float64 | 102.0 |
| unit_cost_cad | float64 | 17.58 |
| value_cad | float64 | 1793.16 |
| ro_id | object | RO-000018 |
| po_line_id | object | POL-0029824 |
| data_status | object | SYNTHETIC |

## stock_policy_current

Current (flat, non-seasonal) reorder point and order-up-to level per branch-SKU. Rows: 194. Primary key: `-`. Foreign keys: `branch_id` -> branches.branch_id, `part_id` -> parts_catalogue.part_id

| Column | Type | Example |
|---|---|---|
| branch_id | object | BR-CCC |
| part_id | object | PRT-00001 |
| reorder_point | int64 | 45 |
| order_up_to | int64 | 102 |
| data_status | object | SYNTHETIC |

## sublet_lines

Sublet and towing costs per RO. Rows: 1,251. Primary key: `sublet_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `vendor_id` -> sublet_vendors.vendor_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| sublet_id | object | SUB-000001 |
| ro_id | object | RO-000059 |
| vendor_id | object | VEN-MEC |
| description | object | Specialist mechanical repair (sublet) |
| sublet_date | object | 2023-10-11 |
| cost_cad | float64 | 406.37 |
| billed_cad | float64 | 479.52 |
| branch_id | object | BR-NFS |
| data_status | object | SYNTHETIC |

## service_appointments

Bookings, appointment dates and outcomes (completed, no-show, cancelled). Rows: 28,437. Primary key: `appointment_id`. Foreign keys: `branch_id` -> branches.branch_id, `customer_id` -> customers.customer_id, `vehicle_id` -> vehicles.vehicle_id, `ro_id` -> repair_orders.ro_id

| Column | Type | Example |
|---|---|---|
| appointment_id | object | APT-026951 |
| branch_id | object | BR-NFS |
| customer_id | object | CUS-000036 |
| vehicle_id | object | VEH-000215 |
| channel | object | Phone |
| requested_service | object | MAINT |
| booked_on | object | 2023-09-18 |
| appointment_date | object | 2023-09-18 |
| appointment_type | object | Service |
| status | object | Cancelled by customer |
| ro_id | object | RO-000001 |
| data_status | object | SYNTHETIC |

## customer_invoices

Invoices raised at delivery, split by bill-to (customer / deductible, insurer, fleet). Rows: 29,453. Primary key: `invoice_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| ro_id | object | RO-000001 |
| branch_id | object | BR-CCC |
| invoice_date | object | 2023-10-24 |
| service_line | object | Collision repair |
| labour_cad | float64 | 528.84 |
| parts_cad | float64 | 1632.85 |
| paint_materials_cad | float64 | 102.9 |
| sublet_cad | float64 | 0.0 |
| fees_cad | float64 | 0.0 |
| discount_cad | float64 | 0.0 |
| invoice_id | object | INV-000001 |
| bill_to_type | object | Customer (deductible) |
| bill_to_id | object | CUS-000023 |
| share_of_ro | float64 | 0.441581 |
| subtotal_cad | float64 | 1000.0 |
| gst_cad | float64 | 50.0 |
| total_cad | float64 | 1050.0 |
| data_status | object | SYNTHETIC |

## payments

Payments and insurer short-pay adjustments. Rows: 28,429. Primary key: `payment_id`. Foreign keys: `invoice_id` -> customer_invoices.invoice_id

| Column | Type | Example |
|---|---|---|
| payment_id | object | PAY-0000001 |
| invoice_id | object | INV-000001 |
| payment_date | object | 2023-10-24 |
| payer_type | object | Customer (deductible) |
| tender | object | Credit card |
| amount_cad | float64 | 1050.0 |
| short_pay_adjustment_cad | float64 | 0.0 |
| data_status | object | SYNTHETIC |

## interbranch_transfers

Internal transfer price for work performed by another branch. Rows: 296. Primary key: `transfer_id`. Foreign keys: `ro_id` -> repair_orders.ro_id, `selling_branch_id` -> branches.branch_id, `performing_branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| transfer_id | object | IBT-000001 |
| ro_id | object | RO-012404 |
| selling_branch_id | object | BR-CCC |
| performing_branch_id | object | BR-SEC |
| transfer_date | object | 2025-05-14 |
| service_type | object | PPF |
| transfer_price_cad | float64 | 428.44 |
| basis | object | Parts, materials & sublet at cost + billed hours x internal  |
| data_status | object | SYNTHETIC |

## materials_issues

Paint & detailing materials issued to ROs. Rows: 6,907. Primary key: `-`. Foreign keys: `ro_id` -> repair_orders.ro_id, `branch_id` -> branches.branch_id

| Column | Type | Example |
|---|---|---|
| ro_id | object | RO-000001 |
| branch_id | object | BR-CCC |
| issue_date | object | 2023-10-20 |
| material_type | object | Paint & refinish materials |
| cost_cad | float64 | 58.08 |
| data_status | object | SYNTHETIC |

## operating_expenses

Monthly operating expenses by branch and head office. Rows: 128. Primary key: `-`.

| Column | Type | Example |
|---|---|---|
| month | object | 2023-10-01 |
| branch_id | object | BR-CCC |
| staff_wages_cad | float64 | 34667.96 |
| rent_cad | float64 | 25728.16 |
| cam_property_tax_cad | float64 | 6019.42 |
| utilities_cad | float64 | 2995.95 |
| shop_supplies_cad | float64 | 9079.55 |
| equipment_maintenance_cad | float64 | 3277.89 |
| software_it_cad | float64 | 1456.31 |
| network_certification_fees_cad | float64 | 2524.27 |
| courier_waste_cad | float64 | 1763.0 |
| courtesy_vehicles_concierge_cad | float64 | 1165.05 |
| card_processing_fees_cad | float64 | 685.35 |
| marketing_cad | float64 | 0.0 |
| insurance_cad | float64 | 0.0 |
| professional_fees_cad | float64 | 0.0 |
| training_certification_cad | float64 | 0.0 |
| data_status | object | SYNTHETIC |

## Chart of accounts

| Code | Name | Type | Statement line |
|---|---|---|---|
| 1000 | Cash - operating account | asset | Cash |
| 1100 | Card & debit processor receivable | asset | Receivables |
| 1110 | Insurer receivables (direct billing) | asset | Receivables |
| 1120 | Fleet & commercial account receivables | asset | Receivables |
| 1200 | Parts inventory - stocked | asset | Inventory |
| 1210 | Special-order parts received for open jobs | asset | Inventory |
| 1220 | Paint, refinish & detailing materials | asset | Inventory |
| 1250 | Work in progress - unbilled repair jobs (at cost) | asset | Work in progress |
| 1300 | Prepaid expenses | asset | Prepaid expenses |
| 1400 | GST input tax credits | asset | Sales tax |
| 1500 | Leasehold improvements | asset | Fixed assets |
| 1510 | Shop equipment (paint booths, frame machines, lifts) | asset | Fixed assets |
| 1520 | Diagnostic, ADAS calibration & IT equipment | asset | Fixed assets |
| 1530 | Vehicles (shuttle & courtesy) | asset | Fixed assets |
| 1590 | Accumulated depreciation | contra_asset | Accumulated depreciation |
| 2000 | Accounts payable - parts & materials suppliers | liability | Accounts payable |
| 2010 | Accounts payable - sublet & operating vendors | liability | Accounts payable |
| 2100 | Accrued payroll | liability | Accrued liabilities |
| 2300 | GST collected | liability | Sales tax |
| 2400 | Income tax payable | liability | Income tax payable |
| 2600 | Revolving operating line of credit | liability | Revolver |
| 2700 | Term loans | liability | Term loans |
| 3000 | Share capital | equity | Share capital |
| 3200 | Retained earnings | equity | Retained earnings |
| 3300 | Dividends declared | equity | Retained earnings |
| 4000 | Collision repair revenue | revenue | Revenue |
| 4100 | Mechanical service revenue | revenue | Revenue |
| 4200 | Detailing revenue | revenue | Revenue |
| 4300 | Glass repair revenue | revenue | Revenue |
| 4400 | Other service revenue (PDR, paint protection, ADAS, fees) | revenue | Revenue |
| 4900 | Discounts, insurer short-pays & adjustments | contra_revenue | Revenue adjustments |
| 4950 | Interbranch service revenue (eliminated on consolidation) | revenue | Interbranch |
| 5000 | Technician labour (wages, overtime & burden) | cogs | Cost of sales |
| 5100 | Parts cost | cogs | Cost of sales |
| 5200 | Paint & materials cost | cogs | Cost of sales |
| 5300 | Subcontracted (sublet) repairs & towing | cogs | Cost of sales |
| 5400 | Warranty rework - parts & sublet | cogs | Cost of sales |
| 5450 | Interbranch sublet cost (eliminated on consolidation) | cogs | Interbranch |
| 5500 | Inventory adjustments & obsolescence | cogs | Cost of sales |
| 6000 | Wages - branch management, estimators, advisors & parts | opex | Staff compensation |
| 6010 | Salaries - group management & administration | opex | Staff compensation |
| 6100 | Rent | opex | Occupancy |
| 6105 | Common-area & property tax charges | opex | Occupancy |
| 6110 | Utilities | opex | Occupancy |
| 6200 | Marketing & advertising | opex | Marketing |
| 6300 | Insurance (garage liability & property) | opex | General & administrative |
| 6310 | Professional fees | opex | General & administrative |
| 6320 | Software & IT (shop management, estimating) | opex | General & administrative |
| 6330 | Collision network & OEM certification fees | opex | General & administrative |
| 6340 | Training & certification | opex | General & administrative |
| 6400 | Shop supplies & equipment maintenance | opex | Shop operations |
| 6410 | Courtesy vehicles, shuttle & concierge | opex | Shop operations |
| 6420 | Courier & waste disposal | opex | Shop operations |
| 6430 | Card processing fees | opex | Shop operations |
| 6900 | Depreciation | opex | Depreciation |
| 7000 | Interest - term loans | other_exp | Interest |
| 7010 | Interest - revolving line | other_exp | Interest |
| 8000 | Income tax expense | tax | Income taxes |
