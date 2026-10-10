"""Operational analytics (Phases 2-7) on the SYNTHETIC data: job costing & profitability, technician productivity, repair
workflow & cycle times, parts & procurement, insurance claims and branch operations. Writes tables for the dashboard and
reports plus findings.json (headline metrics). All findings describe a FICTIONAL business.

Definitions (kept distinct, as in the dashboard):
  Utilisation  = clocked (productive) hours on repair orders / attended hours (available + overtime)
  Efficiency   = billed (flagged / estimating-guide) hours / clocked hours on the same work
  Productivity = billed hours / attended hours  (= utilisation x efficiency)
Fair comparison: each technician's efficiency and comeback rate are compared with the EXPECTED value for the same job mix
(service type) and the same role (indirect standardisation) - never ranked on raw totals.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.config import END, START, TABLES
from src.engineering.load_db import read_all
from src.generate import params as GP

CARRYING_RATE = 0.22          # annual carrying cost of parts inventory (capital, space, obsolescence, insurance) - assumption
CLOSED_NO_WORK = ["Estimate declined", "Repair declined (cash settlement)"]


def save(df, name, index=False):
    d = df.copy()
    d["data_status"] = "SYNTHETIC"
    d.to_csv(TABLES / f"{name}.csv", index=index)
    return df


# ----------------------------------------------------------------------------------------------- Phase 2: job costing
def job_costing(T):
    ro, inv, pay, a = T["repair_orders"], T["customer_invoices"], T["payments"], T["job_assignments"]
    mv, sl, est = T["parts_inventory_movements"], T["sublet_lines"], T["repair_estimates"]
    f = inv.groupby("ro_id").agg(invoice_date=("invoice_date", "first"), labour_rev=("labour_cad", "first"), parts_rev=("parts_cad", "first"),
                                 materials_rev=("paint_materials_cad", "first"), sublet_rev=("sublet_cad", "first"), fees_rev=("fees_cad", "first"),
                                 discount=("discount_cad", "first"), net_revenue=("subtotal_cad", "sum"))
    short = pay.merge(inv[["invoice_id", "ro_id"]], on="invoice_id").groupby("ro_id").short_pay_adjustment_cad.sum()
    iss = mv[mv.movement_type == "ISSUE_TO_RO"]
    parts = -iss[iss.inventory_state != "materials"].groupby("ro_id").value_cad.sum()
    mats = -iss[iss.inventory_state == "materials"].groupby("ro_id").value_cad.sum()
    sub = sl.groupby("ro_id").cost_cad.sum()
    lab = a.groupby("ro_id").labour_cost_cad.sum()
    clk = a.groupby("ro_id").clocked_hours.sum()
    j = ro.set_index("ro_id").join(f).fillna({c: 0.0 for c in f.columns if c != "invoice_date"})
    j["short_pay"] = short.reindex(j.index).fillna(0.0)
    j["net_revenue"] = j.net_revenue - j.short_pay
    j["labour_cost"] = lab.reindex(j.index).fillna(0.0)
    j["parts_cost"] = parts.reindex(j.index).fillna(0.0)
    j["materials_cost"] = mats.reindex(j.index).fillna(0.0)
    j["sublet_cost"] = sub.reindex(j.index).fillna(0.0)
    j["total_cost"] = j[["labour_cost", "parts_cost", "materials_cost", "sublet_cost"]].sum(axis=1)
    j["gross_profit"] = j.net_revenue - j.total_cost
    j["gross_margin_pct"] = np.where(j.net_revenue > 0, j.gross_profit / j.net_revenue * 100, np.nan)
    # estimated cost at estimate time: estimate hours at the branch-group standard efficiency x average loaded wage, + estimated parts cost
    tech = T["technicians"].set_index("tech_id")
    wage = (a.labour_cost_cad.sum() / a.clocked_hours.sum())
    eff_std = (j[j.status == "Delivered"].billed_labour_hours.sum() / clk.reindex(j[j.status == "Delivered"].index).sum())
    j["est_labour_cost"] = j.est_labour_hours / eff_std * wage
    supp = est[est.estimate_type != "Initial"].groupby("ro_id").est_parts_cost_cad.sum()
    j["est_parts_cost"] = j.est_parts_cost_cad + supp.reindex(j.index).fillna(0.0)
    j["est_total_cost"] = j.est_labour_cost + j.est_parts_cost + j.billed_paint_hours * 0.55 * 52 + j.sublet_cost * 0   # materials at standard; sublet excluded
    j["cost_variance"] = j.total_cost - (j.est_total_cost + j.sublet_cost)
    j["clocked_hours"] = clk.reindex(j.index).fillna(0.0)
    j["labour_efficiency"] = np.where(j.clocked_hours > 0, j.billed_labour_hours / j.clocked_hours, np.nan)
    veh = T["vehicles"].set_index("vehicle_id")
    j["vehicle_category"] = j.vehicle_id.map(veh.vehicle_category)
    j["make"] = j.vehicle_id.map(veh.make)
    ins = T["insurers"].set_index("insurer_id")
    j["insurer_category"] = j.insurer_id.map(ins.insurer_category).fillna(j.payer_type)
    # warranty rework cost traced back to the original RO
    w = j[j.payer_type == "Warranty (internal)"]
    rw = w.groupby("warranty_of_ro").total_cost.sum()
    j["warranty_rework_cost"] = rw.reindex(j.index).fillna(0.0)
    j["gross_profit_after_rework"] = j.gross_profit - j.warranty_rework_cost
    # fully loaded view: shop overhead absorbed per clocked hour (TTM branch opex + head office allocated by revenue share) / branch clocked hours
    o = T["operating_expenses"]
    o = o[o.month > pd.Timestamp(END) - pd.Timedelta(days=365)]
    opex = o.drop(columns=["month", "branch_id", "data_status"]).sum(axis=1).groupby(o.branch_id).sum()
    t12 = j[(j.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365)) & (j.status == "Delivered")]
    share = t12.groupby("branch_id").net_revenue.sum() / t12.net_revenue.sum()
    aa = a[a.work_date > pd.Timestamp(END) - pd.Timedelta(days=365)].groupby("branch_id").clocked_hours.sum()
    rate = ((opex.reindex(aa.index).fillna(0) + opex.get("HO", 0.0) * share.reindex(aa.index).fillna(0)) / aa).round(2)
    j["overhead_rate_per_clocked_hour"] = j.performing_branch_id.map(rate)
    j["absorbed_overhead"] = j.clocked_hours * j.overhead_rate_per_clocked_hour
    j["fully_loaded_profit"] = j.gross_profit - j.absorbed_overhead
    j["year"] = j.invoice_date.dt.year
    j = j.reset_index()
    save(rate.rename("overhead_rate_per_clocked_hour").reset_index(), "overhead_absorption_rates")
    return j


def profitability_tables(j):
    d = j[(j.status == "Delivered") & (j.payer_type != "Warranty (internal)") & (j.invoice_date >= START)]
    agg = dict(ros=("ro_id", "count"), net_revenue=("net_revenue", "sum"), labour_rev=("labour_rev", "sum"), labour_cost=("labour_cost", "sum"), parts_rev=("parts_rev", "sum"),
               parts_cost=("parts_cost", "sum"), materials_rev=("materials_rev", "sum"), materials_cost=("materials_cost", "sum"), sublet_cost=("sublet_cost", "sum"),
               gross_profit=("gross_profit", "sum"), rework_cost=("warranty_rework_cost", "sum"), fully_loaded_profit=("fully_loaded_profit", "sum"),
               unprofitable=("fully_loaded_profit", lambda s: int((s < 0).sum())))
    out = {}
    for name, keys in [("service_type", ["service_type", "service_name"]), ("service_line", ["service_line"]), ("vehicle_category", ["vehicle_category"]),
                       ("branch", ["branch_id"]), ("payer", ["insurer_category"]), ("year_line", ["year", "service_line"])]:
        t = d.groupby(keys).agg(**agg).reset_index()
        t["gross_margin_pct"] = t.gross_profit / t.net_revenue * 100
        t["revenue_per_ro"] = t.net_revenue / t.ros
        t["gp_per_ro"] = t.gross_profit / t.ros
        t["labour_margin_pct"] = (1 - t.labour_cost / t.labour_rev.replace(0, np.nan)) * 100
        t["parts_margin_pct"] = (1 - t.parts_cost / t.parts_rev.replace(0, np.nan)) * 100
        t["unprofitable_pct"] = t.unprofitable / t.ros * 100
        out[name] = save(t, f"profitability_by_{name}")
    return out


# ----------------------------------------------------------------------------------------------- Phase 3: technicians
def technicians(T, j):
    ts, a, tech = T["technician_timesheets"], T["job_assignments"], T["technicians"].set_index("tech_id")
    ts = ts[ts.work_date >= START].copy()
    ts["month"] = ts.work_date.dt.to_period("M").astype(str)
    # billed hours credited to technicians pro rata to their clocked hours on each delivered RO (same operation)
    d = j[(j.status == "Delivered") & (j.payer_type != "Warranty (internal)")].set_index("ro_id")
    aa = a[a.internal_rework == 0].merge(d[[f"billed_{g.lower()}_hours" for g in ["BODY", "PAINT", "MECH", "CALIB", "GLASS", "DETAIL", "PPF", "PDR"]] + ["service_type"]],
                                         left_on="ro_id", right_index=True)
    op_clk = aa.groupby(["ro_id", "operation"]).clocked_hours.transform("sum")
    aa["billed_credit"] = [r[f"billed_{op.lower()}_hours"] for op, (_, r) in zip(aa.operation, aa.iterrows())] * (aa.clocked_hours / op_clk)
    aa["month"] = aa.work_date.dt.to_period("M").astype(str)
    m = ts.groupby(["tech_id", "month"]).agg(available=("available_hours", "sum"), overtime=("overtime_hours", "sum"), attended=("attended_hours", "sum"),
                                             productive=("productive_hours", "sum"), paid_absence=("paid_absence_hours", "sum"), training=("training_hours", "sum"))
    bc = aa.groupby(["tech_id", "month"]).agg(billed=("billed_credit", "sum"), clocked_on_billed=("clocked_hours", "sum"), ros=("ro_id", "nunique"))
    m = m.join(bc).fillna(0.0).reset_index()
    m = m.join(tech[["branch_id", "role", "op_groups", "red_seal"]], on="tech_id")
    m["utilisation"] = m.productive / m.attended.replace(0, np.nan)
    m["efficiency"] = m.billed / m.clocked_on_billed.replace(0, np.nan)
    m["productivity"] = m.billed / m.attended.replace(0, np.nan)
    save(m, "technician_productivity_monthly")
    # complexity-adjusted comparison (TTM)
    ttm = aa[aa.work_date > pd.Timestamp(END) - pd.Timedelta(days=365)]
    exp_eff = ttm.groupby(["service_type", "operation"]).apply(lambda g: g.billed_credit.sum() / g.clocked_hours.sum(), include_groups=False).rename("exp")
    ttm = ttm.join(exp_eff, on=["service_type", "operation"])
    ttm["expected_billed"] = ttm.clocked_hours * ttm.exp
    s = ttm.groupby("tech_id").agg(clocked=("clocked_hours", "sum"), billed=("billed_credit", "sum"), expected_billed=("expected_billed", "sum"), ros=("ro_id", "nunique"),
                                   main_service=("service_type", lambda x: x.value_counts().index[0]))
    s["efficiency"] = s.billed / s.clocked
    s["mix_adjusted_efficiency_index"] = s.billed / s.expected_billed                   # 1.00 = as expected for this job mix
    # comebacks attributed to the technicians on the original job, vs expected for the job mix
    w = j[j.payer_type == "Warranty (internal)"].warranty_of_ro
    orig = set(w)
    base_rate = d[d.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=545)].assign(cb=lambda x: x.index.isin(orig)).groupby("service_type").cb.mean()
    ja = a[a.internal_rework == 0].drop_duplicates(["ro_id", "tech_id"]).merge(d[["service_type", "invoice_date"]], left_on="ro_id", right_index=True)
    ja = ja[ja.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=545)]
    ja["cb"] = ja.ro_id.isin(orig)
    ja["exp_cb"] = ja.service_type.map(base_rate)
    r = ja.groupby("tech_id").agg(jobs=("ro_id", "nunique"), comebacks=("cb", "sum"), expected_comebacks=("exp_cb", "sum"))
    s = s.join(r)
    s["comeback_rate_pct"] = s.comebacks / s.jobs * 100
    s["mix_adjusted_comeback_ratio"] = s.comebacks / s.expected_comebacks.replace(0, np.nan)   # 1.00 = as expected
    tm = m[m.month.isin([str(p) for p in pd.period_range(pd.Period(END, "M") - 11, END, freq="M")])].groupby("tech_id")[["attended", "productive", "billed", "overtime"]].sum()
    s = s.join(tm, rsuffix="_ts")
    s["utilisation"] = s.productive / s.attended
    s["productivity"] = s.billed_ts / s.attended
    s = s.join(tech[["branch_id", "role", "red_seal", "hire_date", "termination_date"]])
    # role peers: index vs the role median (not a league table)
    s["vs_role_median_efficiency"] = s.mix_adjusted_efficiency_index / s.groupby("role").mix_adjusted_efficiency_index.transform("median")
    s["evidence"] = np.where(s.jobs >= 60, "Sufficient (60+ jobs)", np.where(s.jobs >= 20, "Limited (20-59 jobs)", "Insufficient (<20 jobs)"))
    save(s.reset_index(), "technician_fair_comparison_ttm")
    return m, s


# ----------------------------------------------------------------------------------------------- Phase 4: workflow & cycle times
STAGES = [("inquiry_date", "estimate_date", "Inquiry -> estimate"), ("estimate_date", "approval_date", "Estimate -> approval"),
          ("approval_date", "ready_date", "Approval -> parts complete (parts waiting)"), ("ready_date", "work_start_date", "Parts complete -> repair start (technician waiting)"),
          ("work_start_date", "work_complete_date", "Repair work"), ("work_complete_date", "qc_date", "Quality control"), ("qc_date", "delivered_date", "Ready -> customer pickup"),
          ("delivered_date", "paid_date", "Delivery -> payment collected")]


def workflow(T, j):
    ro = j.copy()
    ro["ready_date"] = ro[["approval_date", "parts_received_date"]].max(axis=1)
    pay = T["payments"].merge(T["customer_invoices"][["invoice_id", "ro_id"]], on="invoice_id")
    ro["paid_date"] = ro.ro_id.map(pay.groupby("ro_id").payment_date.max())
    for a, b, lab in STAGES:
        ro[lab] = (ro[b] - ro[a]).dt.days
    ro["keys_to_keys_days"] = (ro.delivered_date - ro.vehicle_in_date).dt.days
    ro["total_lead_days"] = (ro.delivered_date - ro.inquiry_date).dt.days
    ro["on_time"] = np.where(ro.qc_date.notna() & ro.promised_date.notna(), ro.qc_date <= ro.promised_date, np.nan)
    ro["original_promise_met"] = np.where(ro.qc_date.notna() & ro.original_promised_date.notna(), ro.qc_date <= ro.original_promised_date, np.nan)
    ro["days_late"] = (ro.qc_date - ro.promised_date).dt.days.clip(lower=0)
    cols = ["ro_id", "branch_id", "performing_branch_id", "service_type", "service_line", "payer_type", "insurer_category", "status", "inquiry_date", "delivered_date",
            "supplement_count", "towed_in", "keys_to_keys_days", "total_lead_days", "on_time", "original_promise_met", "days_late", "csat_score"] + [s[2] for s in STAGES]
    save(ro[cols], "ro_workflow")
    d = ro[(ro.status == "Delivered") & (ro.delivered_date >= START) & (ro.payer_type != "Warranty (internal)")]
    bott = d.groupby("service_line")[[s[2] for s in STAGES]].mean().round(2)
    save(bott.reset_index(), "cycle_stage_means_by_line")
    col = d[d.service_line == "Collision repair"]
    cb = col.groupby(["performing_branch_id"])[[s[2] for s in STAGES]].mean().round(2)
    save(cb.reset_index(), "collision_stage_means_by_branch")
    # work in progress and delays over time (month-end snapshots)
    rows = []
    for m in pd.period_range("2024-01", END, freq="M"):
        at = m.end_time.normalize()
        op = ro[(ro.inquiry_date <= at) & ~(ro.completion_date <= at) & (ro.payer_type != "Warranty (internal)")]
        stage = np.select([op.approval_date.isna() | (op.approval_date > at), op.ready_date > at, op.work_start_date.isna() | (op.work_start_date > at),
                           op.work_complete_date.isna() | (op.work_complete_date > at)], ["Awaiting approval", "Awaiting parts", "Waiting for technician", "In repair"],
                          "Ready / QC / pickup")
        late = (op.promised_date < at) & (op.work_start_date <= at)
        for (b, st), n in pd.Series(1, index=pd.MultiIndex.from_arrays([op.performing_branch_id, stage])).groupby(level=[0, 1]).sum().items():
            rows.append(dict(month=str(m), branch_id=b, stage=st, open_ros=int(n)))
        rows.append(dict(month=str(m), branch_id="ALL", stage="Past promised date (in shop)", open_ros=int(late.sum())))
    save(pd.DataFrame(rows), "wip_snapshot_monthly")
    return ro


# ----------------------------------------------------------------------------------------------- Phase 5: parts & procurement
def parts(T):
    mv, po, cat, sup = T["parts_inventory_movements"], T["supplier_purchase_orders"], T["parts_catalogue"].set_index("part_id"), T["suppliers"].set_index("supplier_id")
    p = po[po.order_date >= START].copy()
    p["lead_days"] = (p.received_date - p.order_date).dt.days
    p["late_days"] = (p.received_date - p.promised_date).dt.days
    p["on_time"] = p.received_date <= p.promised_date
    p["value"] = p.qty_ordered * p.unit_cost_cad
    sp = p[p.po_type.isin(["Special order", "Stock replenishment", "Emergency (stockout)"])].groupby("supplier_id").agg(
        po_lines=("po_line_id", "count"), value=("value", "sum"), avg_lead_days=("lead_days", "mean"), on_time_pct=("on_time", "mean"), backorders=("backorder", "sum"),
        returns=("returned_date", lambda s: int(s.notna().sum())), emergency_orders=("emergency", "sum"))
    sp["on_time_pct"] *= 100
    sp["backorder_pct"] = sp.backorders / sp.po_lines * 100
    sp["return_pct"] = sp.returns / sp.po_lines * 100
    sp = sp.join(sup[["supplier_name", "supplier_type", "lead_time_mean_days"]])
    save(sp.reset_index(), "supplier_performance")
    pm = p.groupby([p.order_date.dt.to_period("M").astype(str), "po_type"]).agg(lines=("po_line_id", "count"), value=("value", "sum")).reset_index()
    save(pm.rename(columns={"order_date": "month"}), "purchase_orders_monthly")
    # stock position, turnover, aging (FIFO), availability
    st = mv[mv.inventory_state == "stock"].sort_values(["movement_date", "movement_id"])
    on = st.groupby(["branch_id", "part_id"]).agg(on_hand=("quantity", "sum"), value=("value_cad", "sum"))
    iss = st[(st.movement_type == "ISSUE_TO_RO") & (st.movement_date > pd.Timestamp(END) - pd.Timedelta(days=365))]
    use = iss.groupby(["branch_id", "part_id"]).agg(units_12m=("quantity", lambda q: -q.sum()), cogs_12m=("value_cad", lambda v: -v.sum()))
    em = po[po.po_type.str.startswith("Emergency") & (po.order_date > pd.Timestamp(END) - pd.Timedelta(days=365))].groupby(["branch_id", "part_id"]).qty_ordered.sum()
    issues_n = iss.groupby(["branch_id", "part_id"]).size()
    em_n = po[po.po_type.str.startswith("Emergency") & (po.order_date > pd.Timestamp(END) - pd.Timedelta(days=365))].groupby(["branch_id", "part_id"]).size()
    rec = st[st.movement_type.isin(["RECEIPT", "OPENING_BALANCE"])]
    ages = {}
    for (b, pid), g in rec.groupby(["branch_id", "part_id"]):
        q = on.at[(b, pid), "on_hand"] if (b, pid) in on.index else 0
        left, age_val = q, 0.0
        for r in g.sort_values("movement_date", ascending=False).itertuples():
            if left <= 0:
                break
            take = min(left, r.quantity)
            age_val += take * (pd.Timestamp(END) - r.movement_date).days
            left -= take
        ages[(b, pid)] = age_val / q if q > 0 else 0.0
    inv = on.join(use).fillna(0.0)
    inv["fifo_age_days"] = pd.Series(ages)
    inv["days_of_cover"] = np.where(inv.units_12m > 0, inv.on_hand / (inv.units_12m / 365), np.inf)
    inv["turnover"] = np.where(inv.value > 0, inv.cogs_12m / inv.value, np.nan)
    inv["carrying_cost_annual"] = inv.value * CARRYING_RATE
    inv["emergency_units_12m"] = em.reindex(inv.index).fillna(0)
    inv["fill_rate_pct"] = (1 - em_n.reindex(inv.index).fillna(0) / issues_n.reindex(inv.index).replace(0, np.nan)) * 100
    inv["age_band"] = pd.cut(inv.fifo_age_days, [-1, 30, 90, 180, 10_000], labels=["0-30 days", "31-90 days", "91-180 days", "180+ days"])
    inv = inv.reset_index().join(cat[["description", "part_category", "default_supplier_id"]], on="part_id")
    save(inv, "parts_stock_position")
    # stocked vs special-order mix (12 months)
    is12 = mv[(mv.movement_type == "ISSUE_TO_RO") & (mv.movement_date > pd.Timestamp(END) - pd.Timedelta(days=365))]
    mix = is12.groupby("inventory_state").value_cad.sum().mul(-1)
    stock_m = []
    for m in pd.period_range("2024-01", END, freq="M"):
        at = m.end_time.normalize()
        v = mv[mv.movement_date <= at].groupby(["branch_id", "inventory_state"]).value_cad.sum()
        for (b, s_), val in v.items():
            stock_m.append(dict(month=str(m), branch_id=b, inventory_state=s_, value=round(val, 2)))
    save(pd.DataFrame(stock_m), "inventory_value_monthly")
    return dict(supplier=sp, stock=inv, mix=mix, po=p)


# ----------------------------------------------------------------------------------------------- Phase 6: insurance claims
def claims(T, j, wf):
    cl, inv, pay, ins = T["insurance_claims"], T["customer_invoices"], T["payments"], T["insurers"].set_index("insurer_id")
    c = cl.join(ins[["insurer_name", "insurer_category"]], on="insurer_id")
    c["approval_days"] = (c.approval_date - c.submitted_date).dt.days
    c["approved_vs_estimate_pct"] = c.approved_value_cad / c.estimate_value_cad * 100
    ii = inv[inv.bill_to_type == "Insurer"].merge(pay.groupby("invoice_id").agg(paid=("payment_date", "max"), cash=("amount_cad", "sum"),
                                                                                  short=("short_pay_adjustment_cad", "sum")), on="invoice_id", how="left")
    ii["payment_days"] = (ii.paid - ii.invoice_date).dt.days
    ii["outstanding"] = np.where(ii.paid.isna(), ii.total_cad, 0.0)
    ii["age_days"] = np.where(ii.paid.isna(), (pd.Timestamp(END) - ii.invoice_date).dt.days, np.nan)
    ii = ii.join(ins[["insurer_name", "insurer_category"]], on="bill_to_id")
    c = c.join(ii.groupby("ro_id").agg(insurer_invoiced=("total_cad", "sum"), payment_days=("payment_days", "mean"), outstanding=("outstanding", "sum"),
                                       short_pay=("short", "sum")), on="ro_id")
    c = c.join(wf.set_index("ro_id")[["keys_to_keys_days", "total_lead_days", "status", "branch_id"]], on="ro_id")
    save(c, "claims_detail")
    by = c[c.submitted_date >= START].groupby(["insurer_category", "insurer_name"]).agg(
        claims=("claim_id", "count"), avg_approval_days=("approval_days", "mean"), approved_vs_estimate_pct=("approved_vs_estimate_pct", "mean"),
        supplement_rate_pct=("supplement_count", "mean"), avg_payment_days=("payment_days", "mean"), outstanding=("outstanding", "sum"),
        short_pays=("short_pay", "sum"), avg_keys_to_keys=("keys_to_keys_days", "mean"), admin_hours=("admin_hours", "sum"), contacts_per_claim=("insurer_contacts", "mean")).reset_index()
    by["supplement_rate_pct"] *= 100
    save(by, "claims_by_insurer")
    ct = c[c.submitted_date >= START].groupby("claim_type").agg(claims=("claim_id", "count"), avg_keys_to_keys=("keys_to_keys_days", "mean"),
                                                                avg_total_lead=("total_lead_days", "mean"), avg_approval_days=("approval_days", "mean"),
                                                                avg_deductible=("deductible_cad", "mean")).reset_index()
    save(ct, "claims_by_type")
    op = ii[ii.paid.isna()]
    ag = op.groupby(["insurer_category", "insurer_name", pd.cut(op.age_days, [-1, 30, 60, 90, 10_000], labels=["0-30", "31-60", "61-90", "90+"])], observed=False).outstanding.sum()
    save(ag.unstack(fill_value=0.0).reset_index(), "insurer_receivables_aging_30sep2026")
    return c, ii


# ----------------------------------------------------------------------------------------------- Phase 7: branch operations
def branches(T, j, wf, m):
    d = wf[(wf.status == "Delivered") & (wf.delivered_date >= START) & (wf.payer_type != "Warranty (internal)")].copy()
    d["year"] = d.delivered_date.dt.year
    jj = j.set_index("ro_id")
    d["net_revenue"] = d.ro_id.map(jj.net_revenue)
    d["gross_profit"] = d.ro_id.map(jj.gross_profit)
    k = d.groupby(["year", "branch_id"]).agg(ros_completed=("ro_id", "count"), net_revenue=("net_revenue", "sum"), gross_profit=("gross_profit", "sum"),
                                              avg_keys_to_keys=("keys_to_keys_days", "mean"), on_time_pct=("on_time", "mean"), csat=("csat_score", "mean"),
                                              parts_wait_days=("Approval -> parts complete (parts waiting)", "mean"))
    k["revenue_per_ro"] = k.net_revenue / k.ros_completed
    k["on_time_pct"] *= 100
    mm = m.assign(year=m.month.str[:4].astype(int)).groupby(["year", "branch_id"])[["attended", "productive", "billed", "available", "overtime"]].sum()
    k = k.join(mm)
    k["technician_utilisation"] = k.productive / k.attended
    k["technician_productivity"] = k.billed / k.attended
    bays = pd.Series({b[0]: b[5] for b in GP.BRANCHES})
    k["repair_bays"] = k.index.get_level_values("branch_id").map(bays)
    save(k.reset_index(), "branch_operations_annual")
    return k


def run():
    T = read_all()
    ro = T["repair_orders"]
    ro["completion_date"] = ro.delivered_date.where(ro.status == "Delivered", ro.closed_date.where(ro.status.isin(
        ["Total loss", "Estimate declined", "Repair declined (cash settlement)", "Estimate declined (diagnostic fee)"])))
    j = job_costing(T)
    save(j.drop(columns=["data_status"], errors="ignore"), "ro_job_costing")
    pt = profitability_tables(j)
    m, s = technicians(T, j)
    wf = workflow(T, j)
    pr = parts(T)
    c, ii = claims(T, j, wf)
    br = branches(T, j, wf, m)
    d = j[(j.status == "Delivered") & (j.payer_type != "Warranty (internal)")]
    ttm = d[d.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365)]
    wft = wf[(wf.status == "Delivered") & (wf.delivered_date > pd.Timestamp(END) - pd.Timedelta(days=365)) & (wf.payer_type != "Warranty (internal)")]
    col = wft[wft.service_line == "Collision repair"]
    mt = m[m.month.isin([str(p) for p in pd.period_range(pd.Period(END, "M") - 11, END, freq="M")])]
    ct = c[c.submitted_date > pd.Timestamp(END) - pd.Timedelta(days=365)]
    stock = pr["stock"]
    K = {
        "ttm_net_revenue": float(ttm.net_revenue.sum()), "ttm_ros": int(len(ttm)), "ttm_gp": float(ttm.gross_profit.sum()),
        "ttm_gm_pct": float(ttm.gross_profit.sum() / ttm.net_revenue.sum() * 100), "unprofitable_ros_pct": float((ttm.fully_loaded_profit < 0).mean() * 100),
        "unprofitable_ros": int((ttm.fully_loaded_profit < 0).sum()), "unprofitable_loss": float(-ttm[ttm.fully_loaded_profit < 0].fully_loaded_profit.sum()),
        "negative_gp_ros": int((ttm.gross_profit < 0).sum()), "overhead_rate": float((ttm.absorbed_overhead.sum() / ttm.clocked_hours.sum())),
        "rework_cost_ttm": float(j[(j.payer_type == "Warranty (internal)") & (j.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365))].total_cost.sum()),
        "comeback_rate_pct": float(j[(j.payer_type == "Warranty (internal)") & (j.inquiry_date > pd.Timestamp(END) - pd.Timedelta(days=365))].shape[0] / max(len(ttm), 1) * 100),
        "utilisation": float(mt.productive.sum() / mt.attended.sum()), "efficiency": float(mt.billed.sum() / mt.clocked_on_billed.sum()),
        "productivity": float(mt.billed.sum() / mt.attended.sum()), "overtime_share": float(mt.overtime.sum() / mt.available.sum()),
        "collision_k2k": float(col.keys_to_keys_days.mean()), "collision_lead": float(col.total_lead_days.mean()),
        "collision_parts_wait": float(col["Approval -> parts complete (parts waiting)"].mean()), "collision_tech_wait": float(col["Parts complete -> repair start (technician waiting)"].mean()),
        "collision_approval_days": float(col["Estimate -> approval"].mean()), "collision_on_time": float(np.nanmean(col.on_time.astype(float)) * 100),
        "collision_original_promise": float(np.nanmean(col.original_promise_met.astype(float)) * 100), "supplement_rate": float(col.supplement_count.mean() * 100),
        "all_on_time": float(np.nanmean(wft.on_time.astype(float)) * 100), "csat": float(wft.csat_score.mean()),
        "csat_late": float(wft[wft.on_time == 0].csat_score.mean()), "csat_ontime": float(wft[wft.on_time == 1].csat_score.mean()),
        "open_ros": int(((ro.inquiry_date <= END) & ro.completion_date.isna() & (ro.payer_type != "Warranty (internal)")).sum()),
        "stock_value": float(stock.value.sum()), "stock_aged_180": float(stock[stock.fifo_age_days > 180].value.sum()),
        "carrying_cost": float(stock.value.sum() * CARRYING_RATE), "emergency_orders_12m": int(pr["po"][(pr["po"].emergency == 1) & (pr["po"].order_date > pd.Timestamp(END) - pd.Timedelta(days=365))
                                                                                                           & pr["po"].po_type.str.startswith("Emergency")].shape[0]),
        "special_order_share": float(pr["mix"].get("job", 0) / pr["mix"][["job", "stock"]].sum() * 100),
        "claims_ttm": int(len(ct)), "approval_days_drp": float(ct[ct.insurer_category.str.startswith("DRP")].approval_days.mean()),
        "approval_days_nondrp": float(ct[ct.insurer_category.str.startswith("Non-DRP")].approval_days.mean()),
        "insurer_outstanding": float(ii.outstanding.sum()), "insurer_payment_days": float(ii[ii.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365)].payment_days.mean()),
        "claims_admin_hours": float(ct.admin_hours.sum()), "approved_vs_estimate": float(ct.approved_vs_estimate_pct.mean()),
    }
    findings = [
        f"Parts waiting is the largest delay in collision repair: {K['collision_parts_wait']:.1f} days on average between approval and parts complete, vs "
        f"{K['collision_tech_wait']:.1f} days waiting for a technician.",
        f"Supplements (hidden damage) occur on {K['supplement_rate']:.0f}% of collision jobs; only {K['collision_original_promise']:.0f}% of collision jobs meet the ORIGINAL promise "
        f"date, {K['collision_on_time']:.0f}% meet the revised promise.",
        f"Late jobs score {K['csat_late']:.2f} / 5 in customer surveys vs {K['csat_ontime']:.2f} for on-time jobs.",
        f"{K['unprofitable_ros']} ROs ({K['unprofitable_ros_pct']:.1f}%) did not cover their direct costs plus shop overhead (${K['overhead_rate']:.0f} per clocked hour) in the "
        f"last 12 months - ${K['unprofitable_loss']:,.0f} short; warranty comebacks cost ${K['rework_cost_ttm']:,.0f}.",
        f"Technician utilisation {K['utilisation']:.0%}, efficiency {K['efficiency']:.0%}, productivity {K['productivity']:.0%}; overtime {K['overtime_share']:.1%} of available hours.",
        f"Non-DRP insurers take {K['approval_days_nondrp']:.1f} days to approve vs {K['approval_days_drp']:.1f} for DRP insurers (fictional insurers).",
    ]
    (TABLES / "findings.json").write_text(json.dumps({"metrics": K, "findings": findings, "data_status": "SYNTHETIC - fictional business"}, indent=1, default=float))
    return K


if __name__ == "__main__":
    import time
    t = time.time()
    k = run()
    print(json.dumps(k, indent=1, default=float))
    print(f"{time.time() - t:.0f}s")
