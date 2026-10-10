"""Double-entry general ledger of the FICTIONAL Prairie Auto Care Group, generated from the synthetic operational database.
Every journal entry balances to the cent when posted and carries a BRANCH dimension (BR-SEC / BR-CCC / BR-NFS / HO).

Journal sources -> entries (nothing is a balancing plug):
    Opening balance      31-Dec-2023 position from the warm-up quarter (explicit balances; opening retained earnings = residual)
    Invoicing            delivered ROs: customer / deductible (card, debit, e-transfer), insurer and fleet receivables, revenue by line, GST
    Collections          card settlements; insurer EFTs (short-pays to 4900); fleet EFTs
    Job costing          parts & materials issued to WIP; sublet invoices to WIP; WIP released to cost of sales at delivery;
                         month-end technician-labour WIP accrual (reversed on the 1st)
    Purchasing           parts & materials receipts (stocked, special-order, emergency) with GST ITCs; supplier returns (credit notes)
    Inventory            cycle-count adjustments and obsolescence write-offs
    Payroll              technician payroll from timesheets (regular, paid absence, overtime x1.5, 15% burden); staff payroll
    Operating expenses   rent, prepaid insurance, vendor bills; supplier & vendor payments
    Interbranch          internal transfer price: 5450 (selling branch) / 4950 (performing branch) - eliminated on consolidation
    Fixed assets         capex, straight-line depreciation; equipment-loan draw
    Treasury & tax       daily revolver sweep, month-end cash band, interest, loan principal, quarterly GST, income tax, dividends
    Year-end close       P&L and dividends closed to retained earnings
All amounts are SIMULATED.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import END, EXTERNAL, START
from src.engineering.load_db import read_all
from src.finance import policy as P

END_TS, START_TS = pd.Timestamp(END), pd.Timestamp(START)
MONTHS = pd.period_range(START, END, freq="M")
OB_DATE = pd.Timestamp(P.OB_DATE)
HO = P.HO


def r2(x):
    return float(np.round(x + 1e-12, 2))


@dataclass
class Book:
    rows: list = field(default_factory=list)
    ar_items: list = field(default_factory=list)
    ap_items: list = field(default_factory=list)
    n: int = 0

    def je(self, prefix, date, source, ref, desc, lines, closing=False):
        """lines: (account, amount (+debit / -credit), counterparty, branch)."""
        cents = [int(round(a * 100)) for _, a, _, _ in lines]
        if sum(cents) != 0:
            raise ValueError(f"Unbalanced JE {prefix} {ref}: {sum(cents) / 100}")
        self.n += 1
        jid = f"{prefix}-{self.n:07d}"
        d = pd.Timestamp(date)
        for (acct, _, cp, br), c in zip(lines, cents):
            if c == 0:
                continue
            if acct not in P.ACCOUNTS:
                raise KeyError(acct)
            self.rows.append((jid, d, acct, c / 100 if c > 0 else 0.0, -c / 100 if c < 0 else 0.0, source, ref, cp, desc, closing, br or HO))
        return jid

    def ar(self, item, acct, cp, branch, doc, due, amount, close=None):
        self.ar_items.append(dict(item_id=item, account=acct, counterparty=cp, branch_id=branch, doc_date=pd.Timestamp(doc), due_date=pd.Timestamp(due),
                                  closed_date=pd.Timestamp(close) if close is not None else pd.NaT, amount=r2(amount)))

    def ap(self, item, acct, cp, branch, doc, due, amount):
        self.ap_items.append(dict(item_id=item, account=acct, counterparty=cp, branch_id=branch, doc_date=pd.Timestamp(doc), due_date=pd.Timestamp(due), amount=r2(amount)))


def load_operational():
    T = read_all()
    T["econ"] = pd.read_csv(EXTERNAL / "economic_indicators_monthly.csv", parse_dates=["month"])
    ro = T["repair_orders"]
    ro["completion_date"] = ro.delivered_date.where(ro.status == "Delivered", ro.closed_date.where(ro.status.isin(
        ["Total loss", "Estimate declined", "Repair declined (cash settlement)", "Estimate declined (diagnostic fee)"])))
    return T


def prime_rate(econ):
    r = econ.set_index(econ.month.dt.to_period("M")).policy_rate_pct.reindex(pd.period_range("2023-12", "2027-12", freq="M")).ffill().bfill()
    return r / 100 + P.PRIME_SPREAD_OVER_POLICY


def months_between(acq, until_period):
    return max(0, (until_period - pd.Period(acq, "M")).n)


def fixed_asset_schedule(until=END):
    """Monthly straight-line depreciation from the month after acquisition; assets owned at 31-Dec-2023 continue from their accumulated depreciation."""
    rows = []
    months = pd.period_range("2024-01", until, freq="M")
    for aid, desc, acct, br, acq, cost, life in P.FIXED_ASSETS:
        monthly = r2(cost / life)
        acc = min(cost, r2(monthly * months_between(acq, pd.Period(P.OB_DATE, "M")))) if pd.Timestamp(acq) <= OB_DATE else 0.0
        m = max(pd.Period(acq, "M") + 1, months[0])
        while m <= months[-1] and acc < cost - 0.005:
            amt = min(monthly, r2(cost - acc))
            acc = r2(acc + amt)
            rows.append({"asset_id": aid, "month": m, "account": acct, "branch_id": br, "depreciation": amt})
            m += 1
    return pd.DataFrame(rows, columns=["asset_id", "month", "account", "branch_id", "depreciation"])


def opening_acc_dep(aid):
    for a, desc, acct, br, acq, cost, life in P.FIXED_ASSETS:
        if a == aid:
            return min(cost, r2(r2(cost / life) * months_between(acq, pd.Period(P.OB_DATE, "M"))))


def wip_components(T):
    """Per RO and date: parts / materials issued and sublet costs (positive = cost added to WIP)."""
    mv = T["parts_inventory_movements"]
    iss = mv[mv.movement_type == "ISSUE_TO_RO"].assign(cost=lambda x: -x.value_cad, kind=lambda x: np.where(x.inventory_state == "materials", "materials", "parts"))
    sub = T["sublet_lines"].assign(cost=lambda x: x.cost_cad, kind="sublet", movement_date=lambda x: x.sublet_date)
    c = pd.concat([iss[["ro_id", "branch_id", "movement_date", "kind", "cost"]], sub[["ro_id", "branch_id", "movement_date", "kind", "cost"]]], ignore_index=True)
    return c.rename(columns={"movement_date": "date"})


def labour_wip_at(T, at):
    """Applied technician labour (standard loaded cost) on ROs open at date `at`, by performing branch."""
    ro, a = T["repair_orders"], T["job_assignments"]
    openro = ro[(ro.work_start_date <= at) & ~(ro.completion_date <= at)].ro_id
    x = a[(a.work_date <= at) & a.ro_id.isin(openro)]
    return x.groupby("branch_id").labour_cost_cad.sum().round(2)


def tech_payroll(T):
    ts = T["technician_timesheets"].copy()
    ts["m"] = ts.work_date.dt.to_period("M")
    ts["gross"] = (ts.scheduled_hours * ts.hourly_wage_cad + ts.overtime_hours * ts.hourly_wage_cad * P.OT_PREMIUM) * (1 + P.LABOUR_BURDEN)
    return ts.groupby(["m", "branch_id"]).gross.sum().round(2)


def opex_frame(T):
    o = T["operating_expenses"].copy()
    o["m"] = o.month.dt.to_period("M")
    return o


# ----------------------------------------------------------------------------------------------- opening position
def post_opening(B: Book, T):
    d = OB_DATE
    br_lines = defaultdict(float)
    lines = [("1000", P.OPENING["cash"], None, HO), ("3000", -P.OPENING["share_capital"], None, HO)]
    for lid, desc, draw, amt, months, spread in P.LOANS:
        if pd.Timestamp(draw) <= d:
            lines.append(("2700", -amt, lid, HO))
    for aid, desc, acct, br, acq, cost, life in P.FIXED_ASSETS:
        if pd.Timestamp(acq) <= d:
            lines += [(acct, cost, aid, br), ("1590", -opening_acc_dep(aid), aid, br)]
    mv = T["parts_inventory_movements"]
    ob = mv[mv.movement_date <= d]
    st_acct = {"stock": "1200", "job": "1210", "materials": "1220"}
    for (st, b), v in ob.groupby(["inventory_state", "branch_id"]).value_cad.sum().items():
        lines.append((st_acct[st], r2(v), None, b))
    # WIP: costs to date on ROs open at 31-Dec-2023 (parts, materials, sublet + applied labour accrual)
    ro = T["repair_orders"]
    c = wip_components(T)
    openro = set(ro[~(ro.completion_date <= d)].ro_id)
    w = c[(c.date <= d) & c.ro_id.isin(openro)].groupby("branch_id").cost.sum()
    lab = labour_wip_at(T, d)
    for b in sorted(set(w.index) | set(lab.index)):
        lines.append(("1250", r2(w.get(b, 0.0) + lab.get(b, 0.0)), None, b))
    # receivables at 31-Dec-2023
    inv, pay = T["customer_invoices"], T["payments"]
    pi = pay.merge(inv[["invoice_id", "ro_id", "branch_id", "invoice_date", "bill_to_type", "bill_to_id", "total_cad"]], on="invoice_id")
    pre_inv = inv[inv.invoice_date <= d]
    for r in pi[(pi.invoice_date <= d) & pi.tender.isin(list(P.CARD_SETTLE_DAYS))].itertuples():
        due = r.payment_date + pd.Timedelta(days=P.CARD_SETTLE_DAYS[r.tender])
        if due > d:
            lines.append(("1100", r2(r.amount_cad), r.tender, r.branch_id))
            B.ar(f"OB-{r.payment_id}", "1100", r.tender, r.branch_id, r.payment_date, due, r.amount_cad)
    paid = pay.groupby("invoice_id").payment_date.max()
    for r in pre_inv[pre_inv.bill_to_type.isin(["Insurer", "Fleet account"])].itertuples():
        pdte = paid.get(r.invoice_id, pd.NaT)
        if r.total_cad > 0 and (pd.isna(pdte) or pdte > d):
            acct = "1110" if r.bill_to_type == "Insurer" else "1120"
            lines.append((acct, r2(r.total_cad), r.bill_to_id, r.branch_id))
            B.ar(f"OB-{r.invoice_id}", acct, r.bill_to_id, r.branch_id, r.invoice_date, r.invoice_date + pd.Timedelta(days=30), r.total_cad, pdte)
    # payables at 31-Dec-2023
    po = T["supplier_purchase_orders"]
    for r in po[(po.received_date <= d)].itertuples():
        due = r.received_date + pd.Timedelta(days=P.SUPPLIER_TERMS[r.supplier_id])
        if due > d:
            v = r2(r.qty_ordered * r.unit_cost_cad)
            amt = r2(v * (1 + P.GST_RATE))
            credit = 0.0
            if pd.notna(r.returned_date) and r.returned_date <= d:
                credit = amt
            if amt - credit > 0.004:
                lines.append(("2000", -r2(amt - credit), r.supplier_id, r.branch_id))
                B.ap(f"OB-{r.po_line_id}", "2000", r.supplier_id, r.branch_id, r.received_date, due, amt - credit)
    sl = T["sublet_lines"]
    for r in sl[sl.sublet_date <= d].itertuples():
        due = r.sublet_date + pd.Timedelta(days=P.VENDOR_TERMS_DAYS)
        if due > d:
            amt = r2(r.cost_cad * (1 + P.GST_RATE))
            lines.append(("2010", -amt, r.vendor_id, r.branch_id))
            B.ap(f"OB-{r.sublet_id}", "2010", r.vendor_id, r.branch_id, r.sublet_date, due, amt)
    o = opex_frame(T)
    dec = o[o.m == pd.Period("2023-12", "M")]
    for r in dec.itertuples():
        for col, a_br, a_ho, v, k in P.OPEX_MAP:
            amt = float(getattr(r, col, 0.0) or 0.0)
            acct = a_ho if r.branch_id == HO else a_br
            if k == "vendor" and amt:
                gross = r2(amt * (1 + (P.GST_RATE if acct in P.GST_TAXABLE_OPEX else 0)))
                lines.append(("2010", -gross, v, r.branch_id))
                B.ap(f"OB-{acct}-{r.branch_id}", "2010", v, r.branch_id, d, pd.Timestamp("2024-01-20"), gross)
    # accrued payroll: second half of December (technicians + staff)
    tp = tech_payroll(T)
    for b in ["BR-CCC", "BR-NFS", "BR-SEC", HO]:
        tech = tp.get((pd.Period("2023-12", "M"), b), 0.0)
        staff = float(dec[dec.branch_id == b].staff_wages_cad.sum())
        acc = r2((tech + staff) * (1 - P.PAYROLL_FIRST_HALF))
        if acc:
            lines.append(("2100", -acc, None, b))
    # GST: Q4-2023 net position (collected on Q4 invoices less ITCs on Q4 purchases, sublets and taxable opex), remitted 31-Jan-2024
    q4 = (pd.Timestamp("2023-10-01"), d)
    col = inv[(inv.invoice_date >= q4[0]) & (inv.invoice_date <= d)].gst_cad.sum()
    rec = po[(po.received_date >= q4[0]) & (po.received_date <= d)]
    itc = (rec.qty_ordered * rec.unit_cost_cad).sum() * P.GST_RATE + sl[(sl.sublet_date >= q4[0]) & (sl.sublet_date <= d)].cost_cad.sum() * P.GST_RATE
    oq = o[(o.m >= pd.Period("2023-10", "M")) & (o.m <= pd.Period("2023-12", "M"))]
    for col_, a_br, a_ho, v, k in P.OPEX_MAP:
        if k != "payroll" and col_ in oq:
            for r in oq.itertuples():
                acct = a_ho if r.branch_id == HO else a_br
                if acct in P.GST_TAXABLE_OPEX:
                    itc += float(getattr(r, col_) or 0.0) * P.GST_RATE
    lines.append(("2300", -r2(col - itc), "Canada Revenue Agency", HO))
    lines.append(("2400", -P.OPENING["income_tax_2023"], "Canada Revenue Agency", HO))
    resid = -r2(sum(a for _, a, _, _ in lines))
    lines.append(("3200", resid, None, HO))                                        # opening retained earnings = derived residual (documented)
    B.je("OB", d, "Opening balance", "OB-2023", "Opening statement of financial position at 31-Dec-2023", lines)
    return lab


# ----------------------------------------------------------------------------------------------- invoicing & collections
def post_invoicing(B: Book, T):
    inv, pay, ro = T["customer_invoices"], T["payments"], T["repair_orders"].set_index("ro_id")
    inv = inv[inv.invoice_date >= START_TS]
    tender = pay.groupby("invoice_id").tender.first()
    paid_on = pay.groupby("invoice_id").payment_date.max()
    for rid, g in inv.groupby("ro_id", sort=False):
        f = g.iloc[0]
        line = ro.at[rid, "service_line"]
        br = f.branch_id
        d = f.invoice_date
        gross = r2(f.labour_cad + f.parts_cad + f.paint_materials_cad + f.sublet_cad + f.fees_cad)
        if r2(g.total_cad.sum()) == 0:
            continue
        lines = []
        for r in g.itertuples():
            if r.total_cad <= 0:
                continue
            if r.bill_to_type.startswith("Customer"):
                t = tender.get(r.invoice_id, "Credit card")
                if t in P.CARD_SETTLE_DAYS:
                    lines.append(("1100", r.total_cad, t, br))
                    B.ar(r.invoice_id, "1100", t, br, d, d + pd.Timedelta(days=P.CARD_SETTLE_DAYS[t]), r.total_cad)
                else:
                    lines.append(("1000", r.total_cad, r.bill_to_id, br))
            else:
                acct = "1110" if r.bill_to_type == "Insurer" else "1120"
                lines.append((acct, r.total_cad, r.bill_to_id, br))
                B.ar(r.invoice_id, acct, r.bill_to_id, br, d, d + pd.Timedelta(days=30), r.total_cad, paid_on.get(r.invoice_id, pd.NaT))
        lines += [(P.REV_ACCT[line], -gross, None, br), ("4900", r2(f.discount_cad), None, br), ("2300", -r2(g.gst_cad.sum()), "Canada Revenue Agency", br)]
        B.je("INV", d, "Invoicing", rid, f"{ro.at[rid, 'service_type']} RO {rid} delivered ({ro.at[rid, 'payer_type']})", lines)
    # insurer & fleet settlements
    pi = pay.merge(T["customer_invoices"][["invoice_id", "branch_id", "bill_to_id"]], on="invoice_id")
    for r in pi[(pi.payer_type.isin(["Insurer", "Fleet account"])) & (pi.payment_date >= START_TS)].itertuples():
        acct = "1110" if r.payer_type == "Insurer" else "1120"
        tot = r2(r.amount_cad + r.short_pay_adjustment_cad)
        lines = [("1000", r.amount_cad, r.bill_to_id, r.branch_id), (acct, -tot, r.bill_to_id, r.branch_id)]
        if r.short_pay_adjustment_cad:
            lines.append(("4900", r.short_pay_adjustment_cad, r.bill_to_id, r.branch_id))
        B.je("COL", r.payment_date, "Collections", r.payment_id, f"{r.payer_type} EFT for {r.invoice_id}" + (" (short-paid)" if r.short_pay_adjustment_cad else ""), lines)


# ----------------------------------------------------------------------------------------------- purchasing, inventory & job costing
def post_purchasing_inventory_jobs(B: Book, T):
    po, mv = T["supplier_purchase_orders"], T["parts_inventory_movements"]
    inv_acct = lambda t: "1210" if t == "Special order" else ("1220" if t.startswith("Materials") else "1200")
    rec = po[(po.received_date >= START_TS) & (po.received_date <= END_TS)]
    for r in rec.itertuples():
        v = r2(r.qty_ordered * r.unit_cost_cad)
        g = r2(v * P.GST_RATE)
        due = r.received_date + pd.Timedelta(days=P.SUPPLIER_TERMS[r.supplier_id])
        B.je("RCV", r.received_date, "Purchasing", r.po_line_id, f"{r.po_type} receipt {r.part_id}",
             [(inv_acct(r.po_type), v, r.supplier_id, r.branch_id), ("1400", g, r.supplier_id, r.branch_id), ("2000", -r2(v + g), r.supplier_id, r.branch_id)])
        B.ap(r.po_line_id, "2000", r.supplier_id, r.branch_id, r.received_date, due, v + g)
    ret = po[po.returned_date.notna() & (po.returned_date >= START_TS)]
    for r in ret.itertuples():
        v = r2(r.qty_ordered * r.unit_cost_cad)
        g = r2(v * P.GST_RATE)
        due = r.received_date + pd.Timedelta(days=P.SUPPLIER_TERMS[r.supplier_id])
        B.je("RTN", r.returned_date, "Purchasing", r.po_line_id, "Wrong / damaged special-order part returned (supplier credit note)",
             [("2000", r2(v + g), r.supplier_id, r.branch_id), ("1210", -v, r.supplier_id, r.branch_id), ("1400", -g, r.supplier_id, r.branch_id)])
        B.ap(f"CN-{r.po_line_id}", "2000", r.supplier_id, r.branch_id, r.returned_date, max(due, r.returned_date), -(v + g))
    st_acct = {"stock": "1200", "job": "1210", "materials": "1220"}
    m = mv[(mv.movement_date >= START_TS) & (mv.movement_type == "ISSUE_TO_RO")]
    for (d, b), g in m.groupby(["movement_date", "branch_id"]):
        lines = [(st_acct[s], r2(v), None, b) for s, v in g.groupby("inventory_state").value_cad.sum().items()]
        lines.append(("1250", -r2(sum(a for _, a, _, _ in lines)), None, b))
        B.je("ISS", d, "Job costing", f"ISS-{b}-{d:%Y%m%d}", "Parts & materials issued to repair orders (WIP)", lines)
    for r in mv[(mv.movement_date >= START_TS) & mv.movement_type.isin(["CYCLE_COUNT_ADJ", "WRITE_OFF_OBSOLETE"])].itertuples():
        B.je("ADJ", r.movement_date, "Inventory", r.movement_id, r.movement_type.replace("_", " ").lower(),
             [("1200", r2(r.value_cad), None, r.branch_id), ("5500", -r2(r.value_cad), None, r.branch_id)])
    sl = T["sublet_lines"]
    for r in sl[sl.sublet_date >= START_TS].itertuples():
        g = r2(r.cost_cad * P.GST_RATE)
        B.je("SUB", r.sublet_date, "Job costing", r.sublet_id, r.description, [("1250", r.cost_cad, r.vendor_id, r.branch_id), ("1400", g, r.vendor_id, r.branch_id),
                                                                              ("2010", -r2(r.cost_cad + g), r.vendor_id, r.branch_id)])
        B.ap(r.sublet_id, "2010", r.vendor_id, r.branch_id, r.sublet_date, r.sublet_date + pd.Timedelta(days=P.VENDOR_TERMS_DAYS), r.cost_cad + g)
    # WIP release to cost of sales on completion
    ro = T["repair_orders"]
    c = wip_components(T)
    done = ro[ro.completion_date >= START_TS].set_index("ro_id")
    cc = c[c.ro_id.isin(done.index)].groupby(["ro_id", "kind"]).cost.sum().unstack(fill_value=0.0)
    for rid, r in cc.iterrows():
        o = done.loc[rid]
        w = o.payer_type == "Warranty (internal)"
        acct = {"parts": "5400" if w else "5100", "materials": "5400" if w else "5200", "sublet": "5400" if w else "5300"}
        lines = [(acct[k], r2(r.get(k, 0.0)), None, o.performing_branch_id) for k in ("parts", "materials", "sublet") if r2(r.get(k, 0.0))]
        if not lines:
            continue
        lines.append(("1250", -r2(sum(a for _, a, _, _ in lines)), None, o.performing_branch_id))
        B.je("COS", o.completion_date, "Job costing", rid, "WIP released to cost of sales" + (" (warranty rework)" if w else ""), lines)
    # interbranch transfer price (eliminated on consolidation)
    for r in T["interbranch_transfers"][T["interbranch_transfers"].transfer_date >= START_TS].itertuples():
        B.je("IBT", r.transfer_date, "Interbranch", r.transfer_id, f"Interbranch {r.service_type} work on {r.ro_id}",
             [("5450", r.transfer_price_cad, r.performing_branch_id, r.selling_branch_id), ("4950", -r.transfer_price_cad, r.selling_branch_id, r.performing_branch_id)])


# ----------------------------------------------------------------------------------------------- payroll & operating expenses
def post_payroll_opex(B: Book, T, lab_open):
    tp = tech_payroll(T)
    o = opex_frame(T)
    prev_due = {}
    for m in MONTHS:
        me = m.end_time.normalize()
        for b in ["BR-CCC", "BR-NFS", "BR-SEC", HO]:
            tech = r2(tp.get((m, b), 0.0))
            orow = o[(o.m == m) & (o.branch_id == b)]
            staff = r2(float(orow.staff_wages_cad.sum()))
            lines = ([("5000", tech, None, b)] if tech else []) + ([("6010" if b == HO else "6000", staff, None, b)] if staff else [])
            tot = r2(tech + staff)
            if tot:
                B.je("PRL", me, "Payroll", f"PRL-{b}-{m}", "Payroll accrual (technicians from timesheets; staff)", lines + [("2100", -tot, None, b)])
                first = r2(tot * P.PAYROLL_FIRST_HALF)
                B.je("PRL", m.start_time + pd.Timedelta(days=14), "Payroll", f"PAY1-{b}-{m}", "Payroll run 1", [("2100", first, None, b), ("1000", -first, None, b)])
            prev = prev_due.get(b)
            if prev is None:
                ptech = tp.get((m - 1, b), 0.0)
                pst = float(o[(o.m == m - 1) & (o.branch_id == b)].staff_wages_cad.sum())
                prev = r2((ptech + pst) * (1 - P.PAYROLL_FIRST_HALF))
            if prev:
                B.je("PRL", m.start_time + pd.Timedelta(days=4), "Payroll", f"PAY2-{b}-{m - 1}", "Payroll run 2 (prior month)", [("2100", prev, None, b), ("1000", -prev, None, b)])
            prev_due[b] = r2(tot - r2(tot * P.PAYROLL_FIRST_HALF)) if tot else 0.0
            for r in orow.itertuples():
                for col, a_br, a_ho, v, k in P.OPEX_MAP:
                    if k == "payroll":
                        continue
                    amt = r2(float(getattr(r, col, 0.0) or 0.0))
                    if not amt:
                        continue
                    acct = a_ho if b == HO else a_br
                    g = r2(amt * P.GST_RATE) if acct in P.GST_TAXABLE_OPEX else 0.0
                    if k == "rent":
                        B.je("OPX", m.start_time, "Operating expenses", f"{acct}-{b}-{m}", P.ACCOUNTS[acct]["name"], [(acct, amt, v, b), ("1400", g, v, b), ("1000", -r2(amt + g), v, b)])
                    elif k == "prepaid":
                        if m.month == 1:
                            prem = r2(premium(o, b, m.year))
                            B.je("INS", m.start_time + pd.Timedelta(days=1), "Prepaid expenses", f"INSP-{b}-{m.year}", "Annual insurance premium", [("1300", prem, v, b), ("1000", -prem, v, b)])
                        B.je("INS", me, "Prepaid expenses", f"INSA-{b}-{m}", "Insurance amortisation", [(acct, amt, v, b), ("1300", -amt, v, b)])
                    else:
                        B.je("OPX", me, "Operating expenses", f"{acct}-{col}-{b}-{m}", P.ACCOUNTS[acct]["name"], [(acct, amt, v, b), ("1400", g, v, b), ("2010", -r2(amt + g), v, b)])
                        B.ap(f"{col}-{b}-{m}", "2010", v, b, me, (m + 1).start_time + pd.Timedelta(days=P.OPEX_PAY_DAY - 1), amt + g)
        # technician-labour WIP accrual on open ROs (reversed on the 1st of next month)
        lab = labour_wip_at(T, me)
        for b, v in lab.items():
            v = r2(v)
            if v:
                B.je("WIPL", me, "Job costing", f"WIPL-{b}-{m}", "Technician labour on open ROs carried in WIP (accrual)", [("1250", v, None, b), ("5000", -v, None, b)])
                if m < MONTHS[-1]:
                    B.je("WIPL", (m + 1).start_time, "Job costing", f"WIPR-{b}-{m}", "Reverse labour WIP accrual", [("5000", v, None, b), ("1250", -v, None, b)])
    for b, v in lab_open.items():
        v = r2(v)
        if v:
            B.je("WIPL", START_TS, "Job costing", f"WIPR-{b}-2023-12", "Reverse opening labour WIP accrual", [("5000", v, None, b), ("1250", -v, None, b)])


def premium(o, b, year):
    """Annual insurance premium paid in January = that year's monthly insurance expense (months after Sep-2026 at the Sep-2026 rate)."""
    x = o[(o.branch_id == b) & (o.month.dt.year == year)].sort_values("month")
    vals = list(x.insurance_cad)
    if len(vals) < 12 and vals:
        vals += [vals[-1]] * (12 - len(vals))
    return sum(vals)


def post_capex_dep_loans(B: Book):
    for aid, desc, acct, br, acq, cost, life in P.FIXED_ASSETS:
        if pd.Timestamp(acq) > OB_DATE:
            B.je("CAP", acq, "Capital expenditure", aid, desc, [(acct, cost, None, br), ("1400", r2(cost * P.GST_RATE), None, br), ("1000", -r2(cost * (1 + P.GST_RATE)), None, br)])
    for lid, desc, draw, amt, months, spread in P.LOANS:
        if pd.Timestamp(draw) > OB_DATE:
            B.je("LON", draw, "Financing", f"DRAW-{lid}", desc, [("1000", amt, "Lender", HO), ("2700", -amt, lid, HO)])
    dep = fixed_asset_schedule()
    for (m, br), g in dep.groupby(["month", "branch_id"]):
        amt = r2(g.depreciation.sum())
        B.je("DPR", m.end_time.normalize(), "Depreciation", f"DPR-{br}-{m}", "Monthly straight-line depreciation", [("6900", amt, None, br), ("1590", -amt, None, br)])


def post_settlements(B: Book):
    ar = pd.DataFrame(B.ar_items)
    c = ar[(ar.account == "1100") & (ar.due_date <= END_TS)]
    for (d, cp, br), g in c.groupby(["due_date", "counterparty", "branch_id"]):
        amt = r2(g.amount.sum())
        B.je("SET", d, "Collections", f"SET-{br}-{cp}-{d:%Y%m%d}", f"{cp} settlement ({len(g)} items)", [("1000", amt, cp, br), ("1100", -amt, cp, br)])
    ap = pd.DataFrame(B.ap_items)
    for (acct, d, cp, br), g in ap[ap.due_date <= END_TS].groupby(["account", "due_date", "counterparty", "branch_id"]):
        amt = r2(g.amount.sum())
        if amt:
            B.je("PAY", d, "Supplier payments", f"PAY-{cp}-{br}-{d:%Y%m%d}", f"Payment to {cp} ({len(g)} items)", [(acct, amt, cp, br), ("1000", -amt, cp, br)])


def _frame(B: Book) -> pd.DataFrame:
    gl = pd.DataFrame(B.rows, columns=["je_id", "date", "account", "debit", "credit", "source", "reference", "counterparty", "description", "is_closing", "branch_id"])
    gl["amount"] = gl.debit - gl.credit
    gl["month"] = gl.date.dt.to_period("M")
    return gl


def income_tax(x):
    x = max(0.0, x)
    return P.TAX_SMALL_RATE * min(x, P.SMALL_BUSINESS_LIMIT) + P.TAX_GENERAL_RATE * max(0.0, x - P.SMALL_BUSINESS_LIMIT)


def loan_schedule():
    """Straight-line principal per loan: monthly principal = amount / months, from the month after the draw (or Jan-2024)."""
    rows = []
    for lid, desc, draw, amt, months, spread in P.LOANS:
        pmt = r2(amt / months)
        bal = amt
        m = max(pd.Period(draw, "M") + 1, MONTHS[0]) if pd.Timestamp(draw) > OB_DATE else MONTHS[0]
        for _ in range(months):
            p = min(pmt, r2(bal))
            rows.append(dict(loan_id=lid, month=m, principal=p, spread=spread))
            bal = r2(bal - p)
            m += 1
    return pd.DataFrame(rows)


def post_treasury_tax_and_close(B: Book, T):
    """Interest, principal, GST, tax, daily revolver sweep, month-end cash band, dividends and year-end close (head office)."""
    prime = prime_rate(T["econ"])
    sched = loan_schedule()
    pnl_accts = sorted(k for k, v in P.ACCOUNTS.items() if v["type"] in P.PNL_TYPES)
    base = _frame(B)
    by_m = base.groupby(["month", "account"]).amount.sum().unstack(fill_value=0.0).reindex(columns=list(P.ACCOUNTS), fill_value=0.0)
    by_m = by_m.reindex(pd.period_range("2023-12", END, freq="M"), fill_value=0.0)
    cash_day = base[base.account == "1000"].groupby("date").amount.sum()
    n0 = len(B.rows)
    R = P.REVOLVER

    def tre(f):
        out = defaultdict(float)
        for r in B.rows[n0:]:
            if not r[9] and f(r[1].to_period("M")):
                out[r[2]] += r[3] - r[4]
        return out

    step = lambda x: float(np.ceil(round(x / R["step"], 9)) * R["step"])
    cash = r2(cash_day[cash_day.index <= OB_DATE].sum())
    bal = {lid: (amt if pd.Timestamp(draw) <= OB_DATE else 0.0) for lid, desc, draw, amt, months, spread in P.LOANS}
    spreads = {lid: spread for lid, desc, draw, amt, months, spread in P.LOANS}
    draws = {pd.Period(draw, "M"): (lid, amt) for lid, desc, draw, amt, months, spread in P.LOANS if pd.Timestamp(draw) > OB_DATE}
    rev_bal = 0.0
    ytd_tax, tax_prior = 0.0, P.OPENING["income_tax_2023"]
    lcf = 0.0
    log = []
    for m in MONTHS:
        me = m.end_time.normalize()
        rate_r = prime[m] + R["spread"]
        rev_days, min_day, intra = 0.0, np.inf, 0.0
        for d in pd.date_range(m.start_time, me):
            cash = r2(cash + cash_day.get(d, 0.0))
            if d < me and cash < R["intramonth_floor"] and rev_bal < R["limit"]:
                draw = min(r2(R["limit"] - rev_bal), step(R["intramonth_target"] - cash))
                B.je("REV", d, "Financing", f"REVD-{d:%Y%m%d}", "Revolver draw (intra-month sweep)", [("1000", draw, "Lender", HO), ("2600", -draw, "Lender", HO)])
                cash, rev_bal, intra = r2(cash + draw), r2(rev_bal + draw), intra + draw
            min_day = min(min_day, cash)
            if d < me:
                rev_days += rev_bal
        if m in draws:
            bal[draws[m][0]] = draws[m][1]
        if m.month in (1, 4, 7, 10):
            q = (m - 1).asfreq("Q")
            qm = by_m[[pm.asfreq("Q") == q for pm in by_m.index]]
            col, itc = -r2(qm["2300"].sum()), r2(qm["1400"].sum())
            B.je("GST", me, "GST remittance", f"GST-{q}", f"GST return {q}", [("2300", col, "Canada Revenue Agency", HO), ("1400", -itc, "Canada Revenue Agency", HO),
                                                                              ("1000", -r2(col - itc), "Canada Revenue Agency", HO)])
            cash = r2(cash - (col - itc))
        i_t = p_t = 0.0
        for lid in bal:
            rate = prime[m] + spreads[lid]
            it = r2(bal[lid] * rate / 12)
            ps = sched[(sched.loan_id == lid) & (sched.month == m)].principal.sum()
            ps = min(r2(ps), r2(bal[lid]))
            if it:
                B.je("INT", me, "Financing", f"INT-{lid}-{m}", f"{lid} interest @ {rate:.2%}", [("7000", it, "Lender", HO), ("1000", -it, "Lender", HO)])
            if ps:
                B.je("TLP", me, "Financing", f"TLP-{lid}-{m}", f"{lid} principal", [("2700", ps, lid, HO), ("1000", -ps, "Lender", HO)])
                bal[lid] = r2(bal[lid] - ps)
            i_t, p_t = i_t + it, p_t + ps
        i_r = r2((rev_days + rev_bal) / m.days_in_month * rate_r / 12)
        if i_r:
            B.je("INT", me, "Financing", f"INT-RV-{m}", f"Revolver interest @ {rate_r:.2%} (average daily balance)", [("7010", i_r, "Lender", HO), ("1000", -i_r, "Lender", HO)])
        cash = r2(cash - i_t - p_t - i_r)
        if m.month == 3 and tax_prior > 0:
            B.je("TAX", me, "Income tax", f"TAXPAY-{m.year - 1}", f"Income tax paid for {m.year - 1}", [("2400", tax_prior, "Canada Revenue Agency", HO),
                                                                                                         ("1000", -tax_prior, "Canada Revenue Agency", HO)])
            cash = r2(cash - tax_prior)
            tax_prior = 0.0
        in_ytd = lambda pm: pm.year == m.year and pm <= m
        t = tre(in_ytd)
        yb = by_m.loc[[pm for pm in by_m.index if in_ytd(pm)]]
        pbt = -r2(sum(yb[a].sum() + t.get(a, 0.0) for a in pnl_accts if a != "8000"))
        need = r2(income_tax(pbt - lcf))
        if r2(need - ytd_tax):
            B.je("TAX", me, "Income tax", f"TAXPROV-{m}", "Income tax provision (YTD true-up; small-business rate on first $500K)",
                 [("8000", r2(need - ytd_tax), None, HO), ("2400", -r2(need - ytd_tax), None, HO)])
            ytd_tax = need
        draw = repay = div = 0.0
        if cash < R["min_cash"]:
            draw = min(r2(R["limit"] - rev_bal), step(R["target_cash"] - cash))
        elif cash > R["repay_above"] and rev_bal > 0:
            repay = min(rev_bal, float(np.floor(round((cash - R["target_cash"]) / R["step"], 9)) * R["step"]))
        if draw:
            B.je("REV", me, "Financing", f"REVD-{m}", "Revolver draw (month-end cash band)", [("1000", draw, "Lender", HO), ("2600", -draw, "Lender", HO)])
        if repay:
            B.je("REV", me, "Financing", f"REVR-{m}", "Revolver repayment", [("2600", repay, "Lender", HO), ("1000", -repay, "Lender", HO)])
        rev_bal = r2(rev_bal + draw - repay)
        cash = r2(cash + draw - repay)
        if m.month == 12:
            ni_year = pbt - need
            if rev_bal == 0 and ni_year > 0:
                div = float(np.floor(min(P.DIVIDEND["payout"] * ni_year, max(0.0, cash - P.DIVIDEND["cash_floor"])) / 1000) * 1000)
            if div > 0:
                B.je("DIV", me, "Equity", f"DIV-{m.year}", "Dividend to shareholders", [("3300", div, "Shareholders", HO), ("1000", -div, "Shareholders", HO)])
                cash = r2(cash - div)
            t = tre(lambda pm: pm.year == m.year)
            yb = by_m.loc[[pm for pm in by_m.index if pm.year == m.year]]
            cl = {a: r2(yb[a].sum() + t.get(a, 0.0)) for a in pnl_accts + ["3300"]}
            cl = {a: v for a, v in cl.items() if v}
            B.je("CLS", me, "Year-end close", f"CLOSE-{m.year}", f"Close FY{m.year}", [(a, -v, None, HO) for a, v in cl.items()] + [("3200", r2(sum(cl.values())), None, HO)],
                 closing=True)
            lcf = max(0.0, lcf - pbt) if pbt > 0 else lcf - pbt
            tax_prior, ytd_tax = ytd_tax, 0.0
        log.append(dict(month=str(m), prime_rate=prime[m], term_interest=i_t, revolver_interest=i_r, term_principal=p_t, term_balance=r2(sum(bal.values())),
                        **{f"balance_{lid}": bal[lid] for lid in bal}, revolver_intramonth_draws=intra, revolver_draw=draw, revolver_repay=repay, revolver_balance=rev_bal,
                        dividend=div, month_end_cash=cash, min_daily_cash=min_day, pbt_ytd=pbt, tax_ytd=need, loss_carryforward=lcf, data_status="SIMULATED"))
    return pd.DataFrame(log)


def build():
    T = load_operational()
    B = Book()
    lab_open = post_opening(B, T)
    post_invoicing(B, T)
    post_purchasing_inventory_jobs(B, T)
    post_payroll_opex(B, T, lab_open)
    post_capex_dep_loans(B)
    post_settlements(B)
    treasury = post_treasury_tax_and_close(B, T)
    gl = _frame(B).sort_values(["date", "je_id"], kind="stable").reset_index(drop=True)
    gl.insert(0, "line_no", np.arange(1, len(gl) + 1))
    gl["account_name"] = gl.account.map(lambda a: P.ACCOUNTS[a]["name"])
    gl["data_status"] = "SIMULATED"
    return dict(gl=gl, ar_items=pd.DataFrame(B.ar_items), ap_items=pd.DataFrame(B.ap_items), treasury=treasury, T=T)


if __name__ == "__main__":
    import time
    t = time.time()
    L = build()
    gl = L["gl"]
    print(len(gl), "lines", gl.je_id.nunique(), "JEs", f"{time.time() - t:.0f}s")
    print("debits = credits:", round(gl.debit.sum() - gl.credit.sum(), 2))
    b = gl.groupby("account").amount.sum()
    print(b.round(0).to_string())
