"""Prairie Auto Care Analytics - repair operations & financial intelligence dashboard (15 pages).

Run:  streamlit run dashboard/app.py
Developed by VisiVault Analytics Ltd. - Synthetic demonstration data. Not actual Ultimate Car Care Group records.
Prairie Auto Care Group is a fictional business; insurers, suppliers, customers and staff are fictional.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import APP_BANNER, APP_NAME, BRAND, END, EXTERNAL, FIN_OUT, REPORTS, SYNTH, TABLES  # noqa: E402
from src.finance import forecast as F  # noqa: E402
from src.finance import ratios as R  # noqa: E402

st.set_page_config(page_title=APP_NAME, page_icon="🔧", layout="wide")
FIN = [BRAND["brand"], BRAND["teal"], BRAND["accent"], BRAND["warn"]]          # validated categorical order (4 slots)
UP, DOWN, TOT = BRAND["teal"], BRAND["bad"], BRAND["navy"]
BR_NAME = {"BR-SEC": "SE Concierge", "BR-CCC": "Central Collision", "BR-NFS": "North Full-Service", "HO": "Head office"}
BR_COL = {"SE Concierge": FIN[2], "Central Collision": FIN[0], "North Full-Service": FIN[1], "Head office": BRAND["subtle"]}
PLOT = dict(template="plotly_white", colorway=FIN, font=dict(family="Inter, Helvetica, Arial", size=12), margin=dict(l=10, r=10, t=50, b=10),
            legend=dict(orientation="h", y=-0.2))
st.markdown(f"""<style>
 .block-container {{padding-top: 1.1rem; max-width: 1400px;}}
 .vv-banner {{background: linear-gradient(90deg, {BRAND['navy']} 0%, {BRAND['brand_dark']} 100%); color:#fff; padding:14px 20px; border-radius:12px;
             display:flex; flex-wrap:wrap; gap:10px; justify-content:space-between; align-items:center; margin-bottom:10px;}}
 .vv-banner h1 {{font-size:1.3rem; margin:0; color:#fff;}} .vv-banner span {{font-size:.8rem; opacity:.85}}
 .vv-synth {{background:#fff4e5; border:1px solid #f5c37a; color:#7a4a00; padding:6px 12px; border-radius:8px; font-size:.8rem; font-weight:600;}}
 .kpi {{background:#fff; border:1px solid rgba(11,15,25,.08); border-radius:12px; padding:11px 13px; box-shadow:0 1px 2px rgba(0,0,0,.04); margin-bottom:8px;}}
 .kpi .l {{font-size:.72rem; color:{BRAND['muted']}; text-transform:uppercase; letter-spacing:.04em;}}
 .kpi .v {{font-size:1.35rem; font-weight:700; color:{BRAND['navy']}; margin-top:2px;}} .kpi .d {{font-size:.76rem; margin-top:2px;}}
 .note {{background:{BRAND['brand_light']}; border-left:4px solid {BRAND['brand']}; padding:9px 13px; border-radius:6px; margin:6px 0; font-size:.9rem;}}
 .fc {{background:#efeaf9; border-left:4px solid {BRAND['accent']}; padding:7px 12px; border-radius:6px; margin:6px 0; font-size:.85rem;}}
 @media (max-width: 640px) {{ .kpi .v {{font-size:1.1rem;}} .vv-banner h1 {{font-size:1.05rem;}} }}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------- data
@st.cache_data
def table(name, **kw):
    p = TABLES / f"{name}.csv"
    return pd.read_csv(p, low_memory=False, **kw) if p.exists() else pd.DataFrame()


@st.cache_data
def synth(name, **kw):
    return pd.read_csv(SYNTH / f"{name}.csv", low_memory=False, **kw)


@st.cache_data
def findings():
    p = TABLES / "findings.json"
    return json.loads(p.read_text()) if p.exists() else {"metrics": {}, "findings": []}


@st.cache_data
def jobs():
    j = table("ro_job_costing", parse_dates=["inquiry_date", "invoice_date", "delivered_date", "approval_date", "work_start_date", "qc_date", "promised_date"])
    w = table("ro_workflow").set_index("ro_id")
    for c in ["keys_to_keys_days", "total_lead_days", "on_time", "original_promise_met", "days_late"] + [c for c in w.columns if "->" in c or c == "Repair work"
                                                                                                         or c == "Quality control"]:
        if c in w:
            j[c] = j.ro_id.map(w[c])
    j["branch"] = j.branch_id.map(BR_NAME)
    j["performing_branch"] = j.performing_branch_id.map(BR_NAME)
    j["month"] = j.delivered_date.dt.to_period("M").dt.to_timestamp()
    return j


@st.cache_data
def fbase():
    js = json.loads((TABLES / "fin_forecast_base.json").read_text())
    dv = pd.DataFrame(js["drivers"]).T
    dv.columns = range(1, F.H + 1)
    return {"A": js["A"], "drivers": dv, "opening": js["opening"]}


def stmt(name):
    d = table(f"fin_{name}", index_col=0)
    lab = d["label"].to_dict() if "label" in d else {}
    return d.drop(columns=[c for c in ("label", "data_status") if c in d.columns]), lab


def money(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v / 1e6:,.2f}M" if v >= 1e6 else f"{s}${v:,.0f}"


def acct(v):
    if pd.isna(v):
        return ""
    return "-" if abs(v) < 0.5 else (f"({abs(v):,.0f})" if v < 0 else f"{v:,.0f}")


def fmt_table(df, labels=None):
    x = df.copy()
    if labels:
        x.index = [labels.get(k, k) for k in x.index]
    return pd.DataFrame({c: [acct(v) for v in x[c]] for c in x.columns}, index=x.index)


def kpis(items, per_row=6):
    for i in range(0, len(items), per_row):
        cols = st.columns(min(per_row, len(items) - i))
        for c, (label, value, delta, good) in zip(cols, items[i:i + per_row]):
            color = BRAND["good"] if good is True else (BRAND["bad"] if good is False else BRAND["muted"])
            c.markdown(f"<div class='kpi'><div class='l'>{label}</div><div class='v'>{value}</div><div class='d' style='color:{color}'>{delta or '&nbsp;'}</div></div>",
                       unsafe_allow_html=True)


def show(fig, h=380):
    fig.update_layout(height=h, **PLOT)
    st.plotly_chart(fig, use_container_width=True)


def note(text):
    st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


def fcnote(text):
    st.markdown(f"<div class='fc'>📈 FORECAST - {text}</div>", unsafe_allow_html=True)


def download(df, name, label="Download CSV", index=False):
    st.download_button(label, df.to_csv(index=index).encode(), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")


def download_file(path, label):
    p = Path(path)
    if p.exists():
        st.download_button(label, p.read_bytes(), file_name=p.name, key=f"f_{p.name}")


def waterfall(labels, values, measures, title):
    fig = go.Figure(go.Waterfall(x=labels, y=values, measure=measures, text=[f"{v / 1000:,.0f}K" for v in values], textposition="outside",
                                 increasing=dict(marker_color=UP), decreasing=dict(marker_color=DOWN), totals=dict(marker_color=TOT)))
    fig.update_layout(title=title, yaxis_tickprefix="$", showlegend=False)
    return fig


def pct(v, d=0):
    return "-" if v is None or pd.isna(v) else f"{v * 100:.{d}f}%"


# ----------------------------------------------------------------------------------------------- layout & filters
st.markdown(f"""<div class='vv-banner'><div><h1>{APP_NAME}</h1><span>Fictional multi-location Calgary collision repair & car care group | Data Jan 2024 - Sep 2026 |
Forecast Oct 2026 - Sep 2027</span></div><div class='vv-synth'>⚠ {APP_BANNER}</div></div>""", unsafe_allow_html=True)
PAGES = ["1. Executive Overview", "2. Repair Job Profitability", "3. Technician Productivity", "4. Repair Cycle Times", "5. Parts Inventory",
         "6. Supplier Performance", "7. Insurance Claims", "8. Customer & Service Analytics", "9. Branch Comparison", "10. Income Statement", "11. Balance Sheet",
         "12. Cash Flow", "13. Financial Ratios", "14. Predictive Forecasting", "15. Scenario Simulator"]
J_ALL = jobs()
with st.sidebar:
    st.markdown(f"<div style='font-weight:800;font-size:1.05rem;color:{BRAND['brand_dark']}'>VisiVault Analytics</div>", unsafe_allow_html=True)
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("FILTERS (pages 1-8)")
    dmin, dmax = pd.Timestamp("2024-01-01").date(), pd.Timestamp(END).date()
    dr = st.date_input("Delivery / inquiry date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    fb = st.multiselect("Branch", list(BR_NAME.values())[:3], default=[])
    fl = st.multiselect("Service line", sorted(J_ALL.service_line.unique()), default=[])
    fp = st.multiselect("Payer", sorted(J_ALL.payer_type.unique()), default=[])
    st.divider()
    st.caption("Prairie Auto Care Group is fictional. Its three-location business model and service menu are inspired by a public Calgary auto care group's website "
               "(Oct 2026); every repair order, cost, technician, insurer, customer and financial figure is synthetic. Calgary weather (ECCC) and Bank of Canada rates are real.")
d0, d1 = (pd.Timestamp(dr[0]), pd.Timestamp(dr[1])) if isinstance(dr, tuple) and len(dr) == 2 else (pd.Timestamp(dmin), pd.Timestamp(dmax))


def filt(j, date_col="delivered_date"):
    x = j[(j[date_col] >= d0) & (j[date_col] <= d1)]
    if fb:
        x = x[x.branch.isin(fb)]
    if fl:
        x = x[x.service_line.isin(fl)]
    if fp:
        x = x[x.payer_type.isin(fp)]
    return x


DELIV = filt(J_ALL[(J_ALL.status == "Delivered") & (J_ALL.payer_type != "Warranty (internal)")])
K = findings()["metrics"]


# ----------------------------------------------------------------------------------------------- pages
def p_exec():
    is_m, _ = stmt("income_statement_monthly")
    bs_m, _ = stmt("balance_sheet_monthly")
    ttm = is_m.iloc[:, -12:].sum(axis=1)
    prv = is_m.iloc[:, -24:-12].sum(axis=1)
    b = bs_m.iloc[:, -1]
    d = DELIV
    col = d[d.service_line == "Collision repair"]
    kpis([("Net revenue (TTM)", money(ttm.net_rev), f"{(ttm.net_rev / prv.net_rev - 1) * 100:+.1f}% vs prior 12m", ttm.net_rev >= prv.net_rev),
          ("Gross margin (TTM)", f"{ttm.gross_profit / ttm.net_rev * 100:.1f}%", "after technician labour & parts", None),
          ("EBITDA (TTM)", money(ttm.ebitda), f"{ttm.ebitda / ttm.net_rev * 100:.1f}% margin", ttm.ebitda > 0),
          ("Net income (TTM)", money(ttm.net_income), f"{ttm.net_income / ttm.net_rev * 100:.1f}% margin", ttm.net_income > 0),
          ("Cash 30-Sep-2026", money(b.cash), "revolver undrawn" if b.revolver < 1 else f"revolver {money(b.revolver)}", True),
          ("Insurer receivables", money(b.ar_insurer), f"{K.get('insurer_payment_days', 0):.0f} days to pay (avg)", None),
          ("ROs completed (filter)", f"{len(d):,}", f"{d.net_revenue.sum() / max(len(d), 1):,.0f} avg revenue", None),
          ("Collision keys-to-keys", f"{col.keys_to_keys_days.mean():.1f} days", f"lead time {col.total_lead_days.mean():.1f} days from first call", None),
          ("On time vs promise", pct(np.nanmean(d.on_time.astype(float))), f"original promise {pct(np.nanmean(col.original_promise_met.astype(float)))} (collision)", None),
          ("Customer satisfaction", f"{d.csat_score.mean():.2f} / 5", f"{d.csat_score.notna().sum():,} survey responses", None),
          ("Technician productivity", pct(K.get("productivity")), f"utilisation {pct(K.get('utilisation'))} x efficiency {pct(K.get('efficiency'))}", None),
          ("Work in progress", money(b.wip), f"{K.get('open_ros', 0)} open ROs at cost", None)])
    m = pd.to_datetime(is_m.columns)
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure([go.Bar(x=m, y=is_m.loc[k], name=n, marker_color=c) for k, n, c in [("rev_collision", "Collision", FIN[0]), ("rev_mech", "Mechanical", FIN[1]),
                                                                                             ("rev_glass", "Glass", FIN[2]), ("rev_detail", "Detailing", FIN[3]),
                                                                                             ("rev_other", "Other services", BRAND["subtle"])]])
        fig.update_layout(barmode="stack", title="Revenue by service line (recognised on delivery)", yaxis_tickprefix="$")
        show(fig, 360)
    with c2:
        fig = go.Figure(go.Bar(x=m, y=is_m.loc["ebitda"], marker_color=[UP if v >= 0 else DOWN for v in is_m.loc["ebitda"]]))
        fig.update_layout(title="Monthly EBITDA (SE Concierge opened May-2025)", yaxis_tickprefix="$")
        show(fig, 360)
    st.markdown("**Key findings (synthetic data, fictional business)**")
    for f in findings().get("findings", []):
        st.markdown(f"- {f}")
    rec = table("recommendations")
    if len(rec):
        st.markdown("**Management recommendations - ranked by value / effort (illustrative estimates)**")
        st.dataframe(rec[["rank", "area", "title", "operating_profit_impact_12m", "cash_impact_12m", "effort", "timeframe", "kpis"]].round(0), use_container_width=True, hide_index=True)
        download(rec, "management_recommendations")


def p_profit():
    st.subheader("Repair job profitability")
    st.caption("Job costing per repair order: revenue (after discounts and insurer short-pays) less technician labour at loaded standard cost, parts, paint & materials "
               "and sublet. Warranty rework is traced back to the original RO. Synthetic data.")
    d = DELIV
    gp = d.gross_profit.sum()
    unp = d[d.fully_loaded_profit < 0]
    kpis([("ROs", f"{len(d):,}", None, None), ("Net revenue", money(d.net_revenue.sum()), None, None), ("Job gross profit", money(gp), f"{gp / d.net_revenue.sum() * 100:.1f}% margin", None),
          ("Fully loaded profit", money(d.fully_loaded_profit.sum()), "after shop overhead per clocked hour", None),
          ("Unprofitable ROs", f"{len(unp):,}", f"{money(-unp.fully_loaded_profit.sum())} short of cost + overhead", False if len(unp) else None),
          ("Warranty rework cost", money(d.warranty_rework_cost.sum()), "on these ROs' comebacks", None)])
    c1, c2 = st.columns(2)
    with c1:
        g = d.groupby("service_name").agg(rev=("net_revenue", "sum"), gp=("gross_profit", "sum"), n=("ro_id", "count")).reset_index()
        g["gm"] = g.gp / g.rev * 100
        fig = px.bar(g.sort_values("gp"), x="gp", y="service_name", orientation="h", color="gm", color_continuous_scale="Blues", title="Gross profit by service type (colour = margin %)",
                     labels={"gp": "Gross profit (CAD)", "service_name": "", "gm": "GM %"})
        show(fig, 470)
    with c2:
        comp = d.groupby("service_line")[["labour_cost", "parts_cost", "materials_cost", "sublet_cost", "gross_profit"]].sum()
        comp = comp.div(comp.sum(axis=1), axis=0) * 100
        fig = go.Figure([go.Bar(y=comp.index, x=comp[c], name=n, orientation="h", marker_color=col) for c, n, col in
                         [("labour_cost", "Labour", FIN[0]), ("parts_cost", "Parts", FIN[2]), ("materials_cost", "Materials", FIN[3]), ("sublet_cost", "Sublet", BRAND["subtle"]),
                          ("gross_profit", "Gross profit", FIN[1])]])
        fig.update_layout(barmode="stack", title="Where each revenue dollar goes (%)", xaxis_ticksuffix="%")
        show(fig, 470)
    c1, c2, c3 = st.columns(3)
    with c1:
        v = d.groupby("vehicle_category").agg(rev=("net_revenue", "sum"), gp=("gross_profit", "sum")).assign(gm=lambda x: x.gp / x.rev * 100).reset_index()
        show(px.bar(v, x="vehicle_category", y="gm", title="Margin % by vehicle category", labels={"gm": "GM %", "vehicle_category": ""}), 330)
    with c2:
        b = d.groupby("branch").agg(rev=("net_revenue", "sum"), gp=("gross_profit", "sum")).assign(gm=lambda x: x.gp / x.rev * 100).reset_index()
        show(px.bar(b, x="branch", y="gm", color="branch", color_discrete_map=BR_COL, title="Job margin % by selling branch", labels={"gm": "GM %", "branch": ""}), 330)
    with c3:
        p = d.groupby("insurer_category").agg(rev=("net_revenue", "sum"), gp=("gross_profit", "sum")).assign(gm=lambda x: x.gp / x.rev * 100).reset_index()
        show(px.bar(p, x="gm", y="insurer_category", orientation="h", title="Margin % by payer", labels={"gm": "GM %", "insurer_category": ""}), 330)
    st.markdown("**Estimated vs actual job cost** (labour at standard, parts at estimated cost; positive = over estimate)")
    e = d[d.service_line == "Collision repair"]
    e = e.sample(min(1500, len(e)), random_state=1)
    fig = px.scatter(e, x="est_total_cost", y="total_cost", color="payer_type", opacity=.55, hover_data=["ro_id", "service_type", "cost_variance"],
                     labels={"est_total_cost": "Estimated cost (CAD)", "total_cost": "Actual cost (CAD)"}, title="Collision ROs: estimated vs actual cost")
    mx = float(max(e.est_total_cost.max(), e.total_cost.max())) if len(e) else 1
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", line=dict(color=BRAND["subtle"], dash="dot"), name="Actual = estimate")
    show(fig, 400)
    st.markdown("**Unprofitable repair orders** (do not cover direct cost + shop overhead absorbed per clocked hour)")
    cols = ["ro_id", "branch", "service_name", "payer_type", "vehicle_category", "net_revenue", "labour_cost", "parts_cost", "materials_cost", "sublet_cost", "gross_profit",
            "absorbed_overhead", "fully_loaded_profit", "billed_labour_hours", "clocked_hours", "discount", "short_pay"]
    st.dataframe(unp.sort_values("fully_loaded_profit")[cols].round(2), use_container_width=True, hide_index=True, height=260)
    st.caption("Overhead absorption rate per clocked hour by branch: " + ", ".join(f"{BR_NAME[r.branch_id]} ${r.overhead_rate_per_clocked_hour:,.0f}"
                                                                           for r in table("overhead_absorption_rates").itertuples()))
    download(unp[cols], "unprofitable_repair_orders")
    st.markdown("---")
    st.markdown("### Job-level profitability calculator")
    svc = st.selectbox("Service type (defaults = trailing-12-month medians)", sorted(d.service_name.unique()) if len(d) else [])
    base = J_ALL[(J_ALL.service_name == svc) & (J_ALL.status == "Delivered") & (J_ALL.payer_type != "Warranty (internal)") & (J_ALL.delivered_date > pd.Timestamp(END) - pd.Timedelta(days=365))]
    if len(base):
        med = base.median(numeric_only=True)
        rate = float(med.labour_rev / max(med.billed_labour_hours, .1))
        wage = float((base.labour_cost.sum() / base.clocked_hours.sum()) if base.clocked_hours.sum() else 40)
        c1, c2, c3, c4 = st.columns(4)
        hrs = c1.number_input("Billed labour hours", 0.1, 200.0, float(round(med.billed_labour_hours, 1)), 0.5)
        rt = c1.number_input("Labour rate $/billed hour", 50.0, 300.0, round(rate, 0), 1.0)
        eff = c2.slider("Technician efficiency (billed / clocked)", 0.6, 1.6, float(np.clip(med.labour_efficiency if pd.notna(med.labour_efficiency) else 1.0, .6, 1.6)), 0.01)
        wg = c2.number_input("Loaded technician cost $/clocked hour", 15.0, 90.0, round(wage, 2), 0.5)
        pc = c3.number_input("Parts cost $", 0.0, 50000.0, float(round(med.parts_cost, 0)), 10.0)
        mk = c3.slider("Parts markup (price / cost)", 1.0, 2.5, float(round(med.parts_rev / med.parts_cost, 2)) if med.parts_cost > 0 else 1.4, 0.01)
        mat = c4.number_input("Paint & materials: billed $", 0.0, 10000.0, float(round(med.materials_rev, 0)), 10.0)
        matc = c4.number_input("Paint & materials: cost $", 0.0, 10000.0, float(round(med.materials_cost, 0)), 10.0)
        st.caption("Scenario levers")
        c1, c2, c3 = st.columns(3)
        de = c1.slider("Labour efficiency change %", -30, 30, 0) / 100
        dp = c2.slider("Parts cost change %", -20, 20, 0) / 100
        dpr = c3.slider("Service price change %", -15, 15, 0) / 100

        def calc(eff_, pcost, price):
            rev = (hrs * rt + pc * mk + mat) * (1 + price)
            cost = hrs / eff_ * wg + pcost + matc
            return rev, cost, rev - cost
        r0, c0, g0 = calc(eff, pc, 0)
        r1, c1_, g1 = calc(eff * (1 + de), pc * (1 + dp), dpr)
        kpis([("Revenue", money(r1), f"{r1 - r0:+,.0f}", r1 >= r0), ("Job cost", money(c1_), f"{c1_ - c0:+,.0f}", c1_ <= c0), ("Gross profit", money(g1), f"{g1 - g0:+,.0f}", g1 >= g0),
              ("Gross margin", f"{g1 / r1 * 100:.1f}%" if r1 else "-", f"{(g1 / r1 - g0 / r0) * 100:+.1f} pts" if r0 and r1 else "", g1 / max(r1, 1) >= g0 / max(r0, 1)),
              ("Clocked hours", f"{hrs / (eff * (1 + de)):.1f}", f"vs {hrs / eff:.1f} at current efficiency", None)], per_row=5)
        note("Efficiency changes the cost of a job (fewer clocked hours for the same billed hours). Whether it also creates more revenue depends on demand - see the Scenario Simulator.")


def p_tech():
    st.subheader("Technician productivity")
    note("<b>Utilisation</b> = clocked hours on repair orders / attended hours (available + overtime).  <b>Efficiency</b> = billed (estimating-guide) hours / clocked hours "
         "on the same work.  <b>Productivity</b> = billed hours / attended hours = utilisation x efficiency. Technicians are compared with the EXPECTED efficiency and comeback "
         "rate for their own job mix and role - not ranked on raw totals.")
    m = table("technician_productivity_monthly")
    m["month"] = pd.to_datetime(m.month)
    m["branch"] = m.branch_id.map(BR_NAME)
    m = m[(m.month >= d0.to_period("M").to_timestamp()) & (m.month <= d1)]
    if fb:
        m = m[m.branch.isin(fb)]
    s = m[["available", "attended", "productive", "billed", "clocked_on_billed", "overtime"]].sum()
    labour = DELIV
    kpis([("Available hours", f"{s.available:,.0f}", "scheduled less absence", None), ("Utilisation", pct(s.productive / s.attended), "clocked / attended", None),
          ("Efficiency", pct(s.billed / s.clocked_on_billed), "billed / clocked", None), ("Productivity", pct(s.billed / s.attended), "billed / attended", None),
          ("Overtime", f"{s.overtime:,.0f} h", f"{s.overtime / s.available * 100:.1f}% of available", None),
          ("Labour cost / RO", f"${labour.labour_cost.sum() / max(len(labour), 1):,.0f}", "applied, loaded", None)])
    m["group"] = np.where(m.op_groups.str.contains("BODY|PAINT"), "Collision & refinish", np.where(m.op_groups.str.startswith("MECH"), "Mechanical & tires",
                                                                                                    np.where(m.op_groups.str.contains("DETAIL|PPF"), "Detailing & protection", "Glass, ADAS & PDR")))
    g = m.groupby(["month", "group"])[["attended", "productive", "billed", "overtime", "available"]].sum().reset_index()
    g["utilisation"] = g.productive / g.attended * 100
    g["productivity"] = g.billed / g.attended * 100
    c1, c2 = st.columns(2)
    with c1:
        show(px.line(g, x="month", y="utilisation", color="group", title="Utilisation % by technician group (capacity pressure)", labels={"utilisation": "%", "month": ""}), 340)
    with c2:
        g["ot_pct"] = g.overtime / g.available * 100
        show(px.bar(g, x="month", y="ot_pct", color="group", barmode="group", title="Overtime as % of available hours", labels={"ot_pct": "%", "month": ""}), 340)
    st.markdown("**By branch and role**")
    br = m.groupby(["branch", "role"])[["attended", "productive", "billed", "clocked_on_billed", "overtime"]].sum()
    br["utilisation_%"] = br.productive / br.attended * 100
    br["efficiency_%"] = br.billed / br.clocked_on_billed * 100
    br["productivity_%"] = br.billed / br.attended * 100
    st.dataframe(br.round(1), use_container_width=True)
    st.markdown("**Complexity-adjusted comparison (last 12 months)** - index 1.00 = exactly what is expected for this technician's job mix")
    f = table("technician_fair_comparison_ttm")
    f["branch"] = f.branch_id.map(BR_NAME)
    if fb:
        f = f[f.branch.isin(fb)]
    cols = ["tech_id", "branch", "role", "jobs", "main_service", "utilisation", "efficiency", "mix_adjusted_efficiency_index", "vs_role_median_efficiency",
            "comeback_rate_pct", "mix_adjusted_comeback_ratio", "overtime", "evidence"]
    st.dataframe(f[cols].sort_values(["branch", "role"]).round(2), use_container_width=True, hide_index=True, height=340)
    st.caption("Technician IDs are synthetic. Use these indices for coaching conversations with context (job mix, apprenticeships, absences) - not as a league table.")
    download(f[cols], "technician_fair_comparison")
    st.markdown("**Scheduling and capacity: daily clocked hours vs regular capacity (select branch)**")
    ts = synth("technician_timesheets", parse_dates=["work_date"])
    bsel = st.selectbox("Branch", list(BR_NAME.values())[:3], index=1)
    bid = {v: k for k, v in BR_NAME.items()}[bsel]
    t = ts[(ts.branch_id == bid) & (ts.work_date >= pd.Timestamp(END) - pd.Timedelta(days=120))].groupby("work_date")[["available_hours", "productive_hours", "overtime_hours"]].sum()
    fig = go.Figure([go.Bar(x=t.index, y=t.productive_hours, name="Clocked on ROs", marker_color=FIN[0]),
                     go.Scatter(x=t.index, y=t.available_hours * .88, name="Regular productive capacity (88% of available)", line=dict(color=BRAND["bad"], width=2))])
    fig.update_layout(title=f"{bsel}: last 120 days")
    show(fig, 330)


def p_cycle():
    st.subheader("Repair workflow & cycle times")
    st.caption("Inquiry -> estimate -> insurer / customer approval -> parts -> scheduling -> repair -> QC -> delivery -> payment. On time = vehicle ready (QC) by the promised "
               "date (revised when a supplement is approved).")
    d = DELIV
    c1, c2, c3 = st.columns(3)
    st_types = c1.multiselect("Service type", sorted(d.service_type.unique()), default=[t for t in ["COL_MIN", "COL_MOD", "COL_MAJ"] if t in set(d.service_type)])
    sup = c2.selectbox("Supplement", ["All", "With supplement", "No supplement"])
    tow = c3.selectbox("Arrival", ["All", "Towed in", "Drove in"])
    x = d[d.service_type.isin(st_types)] if st_types else d
    if sup != "All":
        x = x[x.supplement_count == (1 if sup.startswith("With") else 0)]
    if tow != "All":
        x = x[x.towed_in == (1 if tow == "Towed in" else 0)]
    stg = ["Inquiry -> estimate", "Estimate -> approval", "Approval -> parts complete (parts waiting)", "Parts complete -> repair start (technician waiting)", "Repair work",
           "Quality control", "Ready -> customer pickup", "Delivery -> payment collected"]
    kpis([("Keys-to-keys", f"{x.keys_to_keys_days.mean():.1f} d", f"delivery -> paid {x['Delivery -> payment collected'].mean():.1f} d", None), ("First call -> delivered", f"{x.total_lead_days.mean():.1f} d", None, None),
          ("Estimate -> approval", f"{x['Estimate -> approval'].mean():.1f} d", None, None), ("Parts waiting", f"{x['Approval -> parts complete (parts waiting)'].mean():.1f} d", None, None),
          ("Technician waiting", f"{x['Parts complete -> repair start (technician waiting)'].mean():.1f} d", None, None),
          ("On time (revised promise)", pct(np.nanmean(x.on_time.astype(float))), f"original promise {pct(np.nanmean(x.original_promise_met.astype(float)))}", None)])
    c1, c2 = st.columns([3, 2])
    with c1:
        sm = x[stg[:-1]].mean().reset_index()
        sm.columns = ["stage", "days"]
        fig = px.bar(sm, x="days", y="stage", orientation="h", title="Bottleneck analysis: average days in each repair stage", labels={"stage": ""})
        fig.update_traces(marker_color=[BRAND["bad"] if v == sm.days.max() else FIN[0] for v in sm.days])
        fig.update_yaxes(autorange="reversed")
        show(fig, 380)
    with c2:
        t = x.groupby("month").agg(k2k=("keys_to_keys_days", "mean"), parts=("Approval -> parts complete (parts waiting)", "mean")).reset_index()
        fig = go.Figure([go.Scatter(x=t.month, y=t.k2k, name="Keys-to-keys", line=dict(color=FIN[0], width=3)),
                         go.Scatter(x=t.month, y=t.parts, name="Parts waiting", line=dict(color=FIN[3], width=2))])
        fig.update_layout(title="Monthly averages (days)")
        show(fig, 380)
    w = table("wip_snapshot_monthly")
    w["month"] = pd.to_datetime(w.month)
    ww = w[w.branch_id != "ALL"].assign(branch=lambda q: q.branch_id.map(BR_NAME))
    if fb:
        ww = ww[ww.branch.isin(fb)]
    show(px.bar(ww.groupby(["month", "stage"]).open_ros.sum().reset_index(), x="month", y="open_ros", color="stage", title="Work in progress at month end (open ROs by stage)",
                labels={"open_ros": "Open ROs", "month": ""}), 340)
    st.markdown("**Delayed repairs** (completed later than promised, filtered)")
    late = x[x.days_late > 0].sort_values("days_late", ascending=False)
    cols = ["ro_id", "branch", "performing_branch", "service_name", "payer_type", "supplement_count", "towed_in", "promised_date", "qc_date", "days_late", "keys_to_keys_days", "csat_score"]
    st.dataframe(late[cols].head(300), use_container_width=True, hide_index=True, height=240)
    download(late[cols], "delayed_repairs")
    st.markdown("**Open repair orders at 30-Sep-2026 with model-estimated completion dates** (cycle-time model; 80% band)")
    e = table("estimated_completion_dates_open_ros")
    if len(e):
        e["branch"] = e.branch_id.map(BR_NAME)
        st.dataframe(e.drop(columns=["data_status"], errors="ignore"), use_container_width=True, hide_index=True, height=240)
        download(e, "estimated_completion_dates")


def p_parts():
    st.subheader("Parts inventory")
    note("<b>Stocked parts</b> (oil, filters, brakes, tires, clips, glass kits, film) are held on the shelf and replenished by reorder points. <b>Special-order parts</b> "
         "(bumpers, lamps, panels, sensors, model-specific glass) are bought for a specific repair order and held against that job until installed.")
    s = table("parts_stock_position")
    s["branch"] = s.branch_id.map(BR_NAME)
    if fb:
        s = s[s.branch.isin(fb)]
    iv = table("inventory_value_monthly")
    iv["month"] = pd.to_datetime(iv.month)
    last = iv[iv.month == iv.month.max()].groupby("inventory_state").value.sum()
    po = synth("supplier_purchase_orders", parse_dates=["order_date", "received_date"])
    em = po[po.po_type.str.startswith("Emergency") & (po.order_date > pd.Timestamp(END) - pd.Timedelta(days=365))]
    kpis([("Stocked parts", money(s.value.sum()), f"{len(s)} branch-SKUs", None), ("Special-order parts on hand", money(last.get("job", 0)), "received, awaiting install", None),
          ("Paint & materials", money(last.get("materials", 0)), None, None), ("Turnover (stocked)", f"{s.cogs_12m.sum() / max(s.value.sum(), 1):.1f}x", "12-month issues / stock", None),
          ("Stockouts (emergency orders)", f"{len(em):,}", f"{money((em.qty_ordered * em.unit_cost_cad).sum())} at a premium, 12 m", False),
          ("Carrying cost", money(s.carrying_cost_annual.sum()), "22% p.a. of stocked value", None)])
    c1, c2 = st.columns(2)
    with c1:
        g = iv.groupby(["month", "inventory_state"]).value.sum().reset_index()
        g["inventory_state"] = g.inventory_state.map({"stock": "Stocked parts", "job": "Special-order parts (per job)", "materials": "Paint & materials"})
        show(px.area(g, x="month", y="value", color="inventory_state", title="Inventory at cost by type (month end)", labels={"value": "CAD", "month": ""}), 340)
    with c2:
        a = s.groupby(["age_band", "part_category"], observed=False).value.sum().reset_index()
        show(px.bar(a, x="age_band", y="value", color="part_category", title="Stocked parts by FIFO age", labels={"value": "CAD", "age_band": ""}), 340)
    c1, c2 = st.columns(2)
    with c1:
        e = em.merge(synth("parts_catalogue")[["part_id", "part_category"]], on="part_id")
        e["month"] = e.order_date.dt.to_period("M").dt.to_timestamp()
        show(px.bar(e.groupby(["month", "part_category"]).size().rename("orders").reset_index(), x="month", y="orders", color="part_category",
                    title="Stockouts -> emergency orders by month (tire seasons)", labels={"month": ""}), 330)
    with c2:
        c = s.groupby("part_category").agg(value=("value", "sum"), cogs=("cogs_12m", "sum"), fill=("fill_rate_pct", "mean")).reset_index()
        c["turnover"] = c.cogs / c.value.replace(0, np.nan)
        show(px.bar(c, x="part_category", y="turnover", title="Stock turnover by category (x per year)", labels={"part_category": ""}), 330)
    st.markdown("**Reorder-point recommendations** (seasonal demand forecast + safety stock by ABC class vs the current flat policy)")
    r = table("reorder_point_recommendations")
    r["branch"] = r.branch_id.map(BR_NAME)
    if fb:
        r = r[r.branch.isin(fb)]
    r["change"] = r.recommended_reorder_point - r.current_reorder_point
    st.dataframe(r[["branch", "description", "part_category", "abc_class", "units_last_12m", "forecast_weekly_demand_next_qtr", "service_level", "safety_stock",
                    "current_reorder_point", "recommended_reorder_point", "change", "recommended_order_up_to"]].sort_values("change", ascending=False),
                 use_container_width=True, hide_index=True, height=300)
    download(r, "reorder_point_recommendations")
    st.markdown("**Stock position by branch-SKU**")
    st.dataframe(s[["branch", "description", "part_category", "on_hand", "value", "units_12m", "days_of_cover", "fifo_age_days", "turnover", "fill_rate_pct", "emergency_units_12m"]].round(1),
                 use_container_width=True, hide_index=True, height=260)
    download(s, "parts_stock_position")


def p_supplier():
    st.subheader("Supplier performance")
    st.caption("All suppliers are fictional. On time = received by the supplier's promised date.")
    sp = table("supplier_performance")
    po = synth("supplier_purchase_orders", parse_dates=["order_date", "received_date", "promised_date", "returned_date"])
    p = po[(po.order_date >= d0) & (po.order_date <= d1) & ~po.po_type.str.startswith("Materials")].copy()
    if fb:
        p = p[p.branch_id.map(BR_NAME).isin(fb)]
    p["lead"] = (p.received_date - p.order_date).dt.days
    p["on_time"] = p.received_date <= p.promised_date
    kpis([("PO lines", f"{len(p):,}", None, None), ("Spend", money((p.qty_ordered * p.unit_cost_cad).sum()), None, None), ("On time", pct(p.on_time.mean()), None, None),
          ("Avg lead time", f"{p.lead.mean():.1f} d", "order -> receipt", None), ("Backorders", f"{int(p.backorder.sum()):,}", pct(p.backorder.mean(), 1), None),
          ("Returns (wrong / damaged)", f"{int(p.returned_date.notna().sum()):,}", pct(p.returned_date.notna().mean(), 1), None)])
    c1, c2 = st.columns(2)
    with c1:
        show(px.scatter(sp, x="avg_lead_days", y="on_time_pct", size="value", color="supplier_type", hover_name="supplier_name", title="Lead time vs on-time % (bubble = spend)",
                        labels={"avg_lead_days": "Average lead time (days)", "on_time_pct": "On time %"}), 380)
    with c2:
        q = p[p.po_type == "Special order"].merge(synth("suppliers")[["supplier_id", "supplier_name"]], on="supplier_id")
        show(px.box(q, x="supplier_name", y="lead", points=False, title="Special-order lead time distribution (days)", labels={"supplier_name": "", "lead": "days"}), 380)
    mm = p.groupby([p.order_date.dt.to_period("M").dt.to_timestamp(), "po_type"]).size().rename("lines").reset_index()
    show(px.bar(mm, x="order_date", y="lines", color="po_type", title="Ordering frequency: PO lines by type", labels={"order_date": ""}), 320)
    st.dataframe(sp.drop(columns=["data_status"]).round(1), use_container_width=True, hide_index=True)
    download(sp, "supplier_performance")


def p_claims():
    st.subheader("Insurance claim performance")
    st.warning("All insurers, claims and claim numbers are FICTIONAL. Nothing here describes the performance or payment practices of any real insurance company.")
    c = table("claims_detail", parse_dates=["submitted_date", "approval_date"])
    c = c[(c.submitted_date >= d0) & (c.submitted_date <= d1)]
    c["branch"] = c.branch_id.map(BR_NAME)
    if fb:
        c = c[c.branch.isin(fb)]
    kpis([("Claims", f"{len(c):,}", None, None), ("Approval (DRP)", f"{c[c.insurer_category.str.startswith('DRP')].approval_days.mean():.1f} d", "estimate -> approval", None),
          ("Approval (non-DRP)", f"{c[c.insurer_category.str.startswith('Non-DRP')].approval_days.mean():.1f} d", "independent appraisal", None),
          ("Approved / estimated", f"{c.approved_vs_estimate_pct.mean():.1f}%", "appraiser adjustments", None), ("Supplement rate", pct(c.supplement_count.mean()), None, None),
          ("Outstanding (insurers)", money(c.outstanding.sum()), f"{c.payment_days.mean():.0f} days avg to pay", None)])
    by = table("claims_by_insurer")
    c1, c2 = st.columns(2)
    with c1:
        show(px.bar(by.sort_values("avg_payment_days"), x="avg_payment_days", y="insurer_name", color="insurer_category", orientation="h",
                    title="Average days from invoice to payment (fictional insurers)", labels={"insurer_name": "", "avg_payment_days": "days"}), 380)
    with c2:
        ag = table("insurer_receivables_aging_30sep2026")
        ag = ag.drop(columns=["data_status"]).melt(id_vars=["insurer_category", "insurer_name"], var_name="age", value_name="outstanding")
        show(px.bar(ag, x="outstanding", y="insurer_name", color="age", orientation="h", title="Claims receivable ageing at 30-Sep-2026",
                    labels={"insurer_name": "", "outstanding": "CAD"}), 380)
    c1, c2 = st.columns(2)
    with c1:
        ct = table("claims_by_type")
        show(px.bar(ct, x="claim_type", y=["avg_approval_days", "avg_keys_to_keys"], barmode="group", title="Cycle time by claim type (days)", labels={"claim_type": "", "value": "days"}), 340)
    with c2:
        w = c.groupby(c.submitted_date.dt.to_period("M").dt.to_timestamp()).agg(hours=("admin_hours", "sum"), claims=("claim_id", "count")).reset_index()
        show(px.bar(w, x="submitted_date", y="hours", title="Claim-related administrative workload (hours / month)", labels={"submitted_date": ""}), 340)
    st.dataframe(by.drop(columns=["data_status"]).round(1), use_container_width=True, hide_index=True)
    download(by, "claims_by_insurer")


def p_customer():
    st.subheader("Customer & service analytics")
    d = DELIV
    cust = synth("customers")
    ap = synth("service_appointments", parse_dates=["booked_on", "appointment_date"])
    ap = ap[(ap.appointment_date >= d0) & (ap.appointment_date <= d1)]
    vis = d.groupby("customer_id").ro_id.count()
    kpis([("Customers served", f"{d.customer_id.nunique():,}", None, None), ("Repeat customers", pct((vis > 1).mean()), "2+ completed ROs in the period", None),
          ("Fleet share of revenue", pct(d[d.payer_type == "Fleet account"].net_revenue.sum() / d.net_revenue.sum()), None, None),
          ("Insurer-paid share", pct(d[d.payer_type == "Insurance"].net_revenue.sum() / d.net_revenue.sum()), None, None),
          ("CSAT", f"{d.csat_score.mean():.2f} / 5", None, None), ("No-show / cancel", pct((ap.status != "Completed").mean(), 1), "of service appointments", None)])
    c1, c2 = st.columns(2)
    with c1:
        s = d.groupby("service_name").agg(ros=("ro_id", "count"), revenue=("net_revenue", "sum")).reset_index()
        show(px.treemap(s, path=["service_name"], values="revenue", title="Revenue by service type"), 380)
    with c2:
        cs = d.groupby(["service_line", "branch"]).csat_score.mean().reset_index()
        show(px.bar(cs, x="service_line", y="csat_score", color="branch", barmode="group", color_discrete_map=BR_COL, title="Customer satisfaction by line & branch",
                    labels={"csat_score": "CSAT (1-5)", "service_line": ""}, range_y=[3.5, 5]), 380)
    c1, c2 = st.columns(2)
    with c1:
        wx = pd.read_csv(EXTERNAL / "calgary_weather_daily.csv", parse_dates=["date"])
        snow = wx.groupby(wx.date.dt.to_period("M").dt.to_timestamp()).snow_cm.sum()
        col = J_ALL[J_ALL.service_line == "Collision repair"]
        n = col.groupby(col.inquiry_date.dt.to_period("M").dt.to_timestamp()).size()
        z = pd.DataFrame({"Collision inquiries": n, "Snowfall (cm, ECCC Calgary)": snow}).dropna().reset_index(names="month")
        fig = px.scatter(z, x="Snowfall (cm, ECCC Calgary)", y="Collision inquiries", trendline="ols", hover_data=["month"], title="Collision demand vs monthly snowfall (real weather)")
        show(fig, 360)
    with c2:
        v = d.groupby(["vehicle_category"]).agg(ros=("ro_id", "count")).reset_index()
        show(px.pie(v, names="vehicle_category", values="ros", hole=.5, title="Vehicle mix (completed ROs)"), 360)
    c1, c2 = st.columns(2)
    with c1:
        ch = cust[cust.customer_id.isin(d.customer_id)].acquisition_channel.value_counts().reset_index()
        show(px.bar(ch, x="count", y="acquisition_channel", orientation="h", title="How customers found us (first visit)", labels={"acquisition_channel": ""}), 330)
    with c2:
        ap["lead"] = (ap.appointment_date - ap.booked_on).dt.days
        lt = ap[ap.status == "Completed"].groupby([ap.appointment_date.dt.to_period("M").dt.to_timestamp(), "requested_service"]).lead.mean().reset_index()
        lt = lt[lt.requested_service.isin(["TIRE", "DET", "PPF", "MAINT"])]
        show(px.line(lt, x="appointment_date", y="lead", color="requested_service", title="Days from booking to appointment (seasonal pressure)", labels={"appointment_date": "", "lead": "days"}), 330)
    download(d[["ro_id", "branch", "customer_id", "service_name", "payer_type", "net_revenue", "csat_score"]], "service_detail")


def p_branch():
    st.subheader("Branch comparison")
    note("External revenue is recognised once, by the branch that sold the job. Work done for another branch is charged at an internal transfer price (interbranch "
         "revenue / cost) and eliminated in the consolidated statements. Shared head-office costs are allocated by documented drivers (management view only).")
    bp = table("fin_branch_pnl_annual")
    ops = table("branch_operations_annual")
    yrs = sorted(bp.year.astype(str).unique())
    y = st.radio("Year", yrs, index=len(yrs) - 1, horizontal=True, format_func=lambda v: f"{v} YTD (Jan-Sep)" if v == "2026" else v)
    b = bp[(bp.year.astype(str) == y) & (bp.branch_id != "HO")].copy()
    o = ops[ops.year.astype(str) == y].set_index("branch_id")
    b = b.join(o, on="branch_id", rsuffix="_ops")
    b["branch"] = b.branch_id.map(BR_NAME)
    cols = st.columns(3)
    for c, (_, r) in zip(cols, b.iterrows()):
        c.markdown(f"**{r.branch}**")
        c.markdown(f"<div class='kpi'><div class='l'>External revenue</div><div class='v'>{money(r.external_net_revenue)}</div>"
                   f"<div class='d'>{int(r.ros_completed) if pd.notna(r.ros_completed) else 0:,} ROs · ${r.revenue_per_ro if pd.notna(r.revenue_per_ro) else 0:,.0f} / RO</div></div>"
                   f"<div class='kpi'><div class='l'>Operating profit after allocations</div><div class='v'>{money(r.operating_profit_after_allocations)}</div>"
                   f"<div class='d'>direct {money(r.direct_operating_profit)} · allocated {money(r.allocated_shared_costs)}</div></div>", unsafe_allow_html=True)
    t = b[["branch", "external_net_revenue", "interbranch_revenue", "interbranch_cost", "gross_profit_incl_interbranch", "direct_operating_profit", "allocated_shared_costs",
           "operating_profit_after_allocations", "ros_completed", "revenue_per_ro", "avg_keys_to_keys", "on_time_pct", "csat", "parts_wait_days", "technician_utilisation",
           "technician_productivity", "repair_bays"]].copy()
    t["repair_gross_margin_%"] = t.gross_profit_incl_interbranch / (t.external_net_revenue + t.interbranch_revenue) * 100
    t["revenue_per_bay"] = t.external_net_revenue / t.repair_bays
    st.dataframe(t.set_index("branch").T.round(2), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        m = table("fin_branch_income_statement_monthly")
        m = m[m.branch_id != "HO"]
        m["branch"] = m.branch_id.map(BR_NAME)
        e = m[m.line.isin(["ebit", "ib_rev", "ib_cost"])].groupby(["month", "branch"]).total.sum().reset_index()
        e["month"] = pd.to_datetime(e.month)
        show(px.line(e, x="month", y="total", color="branch", color_discrete_map=BR_COL, title="Monthly operating profit after allocations", labels={"total": "CAD", "month": ""}), 340)
    with c2:
        cf = table("fin_branch_operating_cash_flow_monthly")
        cf["branch"] = cf.branch_id.map(BR_NAME)
        cf = cf[cf.branch_id != "HO"]
        cf["month"] = pd.to_datetime(cf.month)
        show(px.bar(cf, x="month", y="operating_cash_flow", color="branch", color_discrete_map=BR_COL, barmode="group", title="Branch operating cash flow (EBITDA - change in branch working capital)",
                    labels={"operating_cash_flow": "CAD", "month": ""}), 340)
    st.markdown("**Shared-cost allocation assumptions**")
    st.dataframe(table("fin_allocation_assumptions").drop(columns=["data_status"]), use_container_width=True, hide_index=True)
    st.markdown("**Drill-down: branch monthly P&L**")
    pick = st.selectbox("Branch", list(BR_NAME.values()))
    pid = {v: k for k, v in BR_NAME.items()}[pick]
    mm = m if pid != "HO" else table("fin_branch_income_statement_monthly")
    x = mm[mm.branch_id == pid].pivot_table(index="line", columns="month", values="total", aggfunc="sum")
    order = ["rev_collision", "rev_mech", "rev_detail", "rev_glass", "rev_other", "adjustments", "net_rev", "ib_rev", "labour", "parts", "materials", "sublet", "warranty", "ib_cost",
             "gross_profit", "staff", "occupancy", "marketing", "g_and_a", "shop_ops", "ebitda", "da", "ebit"]
    x = x.reindex([k for k in order if k in x.index])
    st.dataframe(fmt_table(x), use_container_width=True, height=420)
    download(x, f"branch_pnl_{pid}", index=True)


def p_is():
    st.subheader("Income statement (consolidated, interbranch eliminated)")
    st.caption("Revenue is recognised on delivery after quality control; costs of open jobs are carried in work in progress at cost. SIMULATED financial information.")
    gran = st.radio("Granularity", ["Annual", "Quarterly", "Monthly"], horizontal=True)
    df, lab = stmt({"Annual": "income_statement_annual", "Quarterly": "income_statement_quarterly", "Monthly": "income_statement_monthly"}[gran])
    df = df.rename(columns={"2026": "2026 YTD (Jan-Sep)"})
    cols = list(df.columns)
    c1, c2 = st.columns(2)
    a = c1.selectbox("Period", cols, index=len(cols) - (2 if gran == "Annual" else 1))
    b = c2.selectbox("Compare with", cols, index=max(0, len(cols) - (3 if gran == "Annual" else 2)))
    comp = pd.DataFrame({a: df[a], b: df[b], "Variance": df[a] - df[b]})
    c1, c2 = st.columns([3, 2])
    with c1:
        st.dataframe(fmt_table(comp, lab), use_container_width=True, height=640)
    with c2:
        x = df[a]
        show(waterfall(["Net revenue", "Labour", "Parts", "Materials & sublet", "Gross profit", "Opex", "EBITDA", "Depreciation", "Interest", "Tax", "Net income"],
                       [x.net_rev, x.labour, x.parts, x.materials + x.sublet + x.warranty + x.inv_adj, 0, x.opex, 0, x.da, x.interest, x.tax, 0],
                       ["absolute", "relative", "relative", "relative", "total", "relative", "total", "relative", "relative", "relative", "total"], f"{a}: revenue to net income"), 430)
        cs, _ = stmt("common_size_annual")
        st.markdown("**Common-size (% of net revenue), annual**")
        st.dataframe(cs.loc[["net_rev", "labour", "parts", "materials", "gross_profit", "staff", "occupancy", "opex", "ebitda", "net_income"]].round(1), use_container_width=True)
    download(df, f"income_statement_{gran.lower()}", index=True)
    download_file(FIN_OUT / "Prairie_Auto_Care_Financial_Statements.xlsx", "Download statements workbook (Excel)")


def p_bs():
    st.subheader("Balance sheet")
    df, lab = stmt("balance_sheet_monthly")
    cols = list(df.columns)
    a = st.select_slider("Month end", cols, value=cols[-1])
    i = cols.index(a)
    b = cols[i - 12] if i >= 12 else cols[0]
    x = df[a]
    kpis([("Total assets", money(x.total_assets), f"vs {money(df.at['total_assets', b])} {b}", None), ("Insurer receivables", money(x.ar_insurer), "direct billing", None),
          ("Work in progress", money(x.wip), "unbilled jobs at cost", None), ("Working capital", money(x.current_assets - x.current_liabilities), f"current ratio {x.current_assets / x.current_liabilities:.2f}", True),
          ("Debt", money(x.revolver + x.term_current + x.term_lt), "term loans + revolver", None), ("A = L + E", "✔ balanced" if abs(x.check) < 0.01 else "✖", f"diff ${x.check:,.2f}", abs(x.check) < 0.01)])
    c1, c2 = st.columns([3, 2])
    with c1:
        st.dataframe(fmt_table(pd.DataFrame({a: x, b: df[b], "Change": x - df[b]}).drop(index="check"), lab), use_container_width=True, height=640)
    with c2:
        mm = pd.to_datetime(df.columns)
        fig = go.Figure([go.Bar(x=mm, y=df.loc[k], name=n, marker_color=c) for k, n, c in [("cash", "Cash", FIN[0]), ("ar_insurer", "Insurer receivables", FIN[1]),
                                                                                          ("wip", "Work in progress", FIN[2]), ("inventory", "Parts", FIN[3]),
                                                                                          ("ppe_net", "Net fixed assets", BRAND["subtle"])]])
        fig.update_layout(barmode="stack", title="Asset composition", yaxis_tickprefix="$")
        show(fig, 310)
        fig = go.Figure([go.Bar(x=mm, y=df.loc[k], name=n, marker_color=c) for k, n, c in [("ap", "Payables", FIN[0]), ("accrued", "Accrued payroll", FIN[1]),
                                                                                          ("term_current", "Loans (current)", FIN[3]), ("term_lt", "Loans (non-current)", FIN[2]),
                                                                                          ("total_equity", "Equity", BRAND["subtle"])]])
        fig.update_layout(barmode="stack", title="Funding composition", yaxis_tickprefix="$")
        show(fig, 310)
    download(df, "balance_sheet_monthly", index=True)


def p_cf():
    st.subheader("Cash flow statement (indirect method)")
    gran = st.radio("Granularity", ["Annual", "Quarterly", "Monthly"], horizontal=True, key="cfg")
    df, lab = stmt({"Annual": "cash_flow_annual", "Quarterly": "cash_flow_quarterly", "Monthly": "cash_flow_monthly"}[gran])
    a = st.selectbox("Period", list(df.columns), index=len(df.columns) - 1, key="cfa")
    x = df[a]
    kpis([("Net income", money(x.net_income), None, None), ("Operating cash flow", money(x.cfo), None, x.cfo > 0), ("Receivables change", money(x.d_ar), "(-) = cash tied up", None),
          ("WIP change", money(x.d_wip), "(-) = cash tied up", None), ("Capital expenditure", money(x.capex), None, None),
          ("Ending cash", money(x.close_cash), "ties to balance sheet ✔" if abs(x.check) < 0.01 else "✖", abs(x.check) < 0.01)])
    c1, c2 = st.columns([2, 3])
    with c1:
        st.dataframe(fmt_table(df[[a]], lab), use_container_width=True, height=600)
    with c2:
        show(waterfall(["Opening cash", "Net income", "Depreciation", "Receivables", "Inventory", "WIP", "Payables", "Other WC", "Capex", "Borrowings", "Repayments", "Dividends", "Ending cash"],
                       [x.open_cash, x.net_income, x.da, x.d_ar, x.d_inv, x.d_wip, x.d_ap, x.d_other, x.capex, x.borrowings, x.repayments, x.dividends, 0],
                       ["absolute"] + ["relative"] * 11 + ["total"], f"Cash bridge {a}"), 440)
        dm, _ = stmt("cash_flow_direct_method")
        st.markdown("**Direct-method view (receipts and payments, by year)**")
        st.dataframe(fmt_table(dm.T.groupby(lambda c: c[:4]).sum().T), use_container_width=True)
    download(df, f"cash_flow_{gran.lower()}", index=True)


def p_ratios():
    st.subheader("Financial ratios (TTM)")
    ann = table("fin_ratios_annual", index_col=0)
    r = table("fin_ratios_monthly_ttm", index_col=0).drop(columns="data_status")
    grp = st.radio("Group", ["Profitability", "Liquidity", "Efficiency", "Solvency"], horizontal=True)
    keys = [d[0] for d in R.DEFINITIONS if d[2] == grp]
    items = []
    for k in keys:
        d = R.DEF[k]
        v = ann.at[k, "TTM Sep-2026"]
        items.append((d[1], money(v) if d[5] == "$" else f"{v:,.2f}{'%' if d[5] == '%' else (' d' if d[5] == 'days' else 'x')}", f"{ann.at[k, 'change_vs_FY2025']:+,.2f} vs FY2025",
                      ann.at[k, "direction"] == "improved"))
    kpis(items)
    sel = st.multiselect("Plot", keys, default=keys[:3], format_func=lambda k: R.DEF[k][1])
    fig = go.Figure([go.Scatter(x=pd.to_datetime(r.columns), y=r.loc[k], name=R.DEF[k][1], line=dict(width=2.5, color=FIN[i % 4])) for i, k in enumerate(sel)])
    fig.update_layout(title=f"{grp} ratios - monthly TTM")
    show(fig, 360)
    st.dataframe(ann.loc[keys, ["ratio", "formula", "FY2024", "FY2025", "TTM Sep-2026", "direction", "meaning", "management_action"]].round(2), use_container_width=True, hide_index=True)
    if grp == "Efficiency":
        ag = table("fin_ar_aging_monthly")
        ag["month"] = pd.to_datetime(ag.month)
        show(px.bar(ag.groupby(["month", "bucket"]).amount.sum().reset_index(), x="month", y="amount", color="bucket", title="Insurer & fleet receivables ageing (month end)",
                    labels={"amount": "CAD", "month": ""}), 320)
    download(ann, "ratio_analysis", index=True)


def p_forecast():
    st.subheader("Predictive forecasting")
    fcnote("Oct 2026 - Sep 2027 values are synthetic projections, shown dashed with an 80% interval. Model accuracy is measured on SYNTHETIC data with time-based "
           "backtests and does not establish real-world prediction accuracy.")
    hist = table("forecast_history")
    fc = table("forecast_next_12_months", parse_dates=["month"])
    comp = table("forecast_model_comparison")
    names = {"revenue_total": "1. Monthly service revenue - total", "revenue_collision": "1. Revenue - collision", "revenue_mechanical": "1. Revenue - mechanical",
             "revenue_detailing": "1. Revenue - detailing", "revenue_glass": "1. Revenue - glass", "revenue_other": "1. Revenue - other services",
             "ros_collision": "2. RO volume - collision", "ros_mechanical": "2. RO volume - mechanical", "ros_detailing": "2. RO volume - detailing", "ros_glass": "2. RO volume - glass",
             "ros_other": "2. RO volume - other", "billed_hours_collision": "2. Demand - collision billed hours", "billed_hours_mechanical": "2. Demand - mechanical billed hours",
             "tech_available_hours_collision": "5. Technician capacity - collision (available hours)", "tech_available_hours_mechanical": "5. Technician capacity - mechanical (available hours)",
             "cash_collections": "6. Expected cash collections"}
    parts_t = sorted(t for t in fc.target.unique() if t.startswith("parts_units_"))
    names.update({t: f"4. Parts demand - {t.replace('parts_units_', '')} (units)" for t in parts_t})
    tgt = st.selectbox("Series", [t for t in names if t in set(fc.target)], format_func=lambda t: names[t])
    f = fc[fc.target == tgt]
    fig = go.Figure()
    h = hist[hist.target == tgt]
    if len(h):
        fig.add_scatter(x=pd.to_datetime(h.month), y=h.actual, name="Simulated history", line=dict(color=TOT, width=3))
    elif tgt.startswith("tech_available") or tgt.startswith("parts_units") or tgt == "cash_collections":
        bt = table("forecast_backtest_predictions")
        hb = bt[(bt.target == tgt)].drop_duplicates("month")
        if len(hb):
            fig.add_scatter(x=pd.to_datetime(hb.month), y=hb.actual, name="Simulated history (backtest months)", line=dict(color=TOT, width=3))
    fig.add_scatter(x=list(f.month) + list(f.month[::-1]), y=list(f.upper80) + list(f.lower80[::-1]), fill="toself", fillcolor="rgba(74,58,167,0.13)", line=dict(width=0), name="80% interval")
    fig.add_scatter(x=f.month, y=f.forecast, name=f"FORECAST ({f.model.iloc[0]})", line=dict(color=BRAND["accent"], width=3, dash="dash"))
    fig.add_vrect(x0="2026-09-30", x1=str(f.month.max().date()), fillcolor="#efeaf9", opacity=.35, line_width=0, annotation_text="FORECAST", annotation_position="top left")
    fig.update_layout(title=names[tgt])
    show(fig, 420)
    c = comp[comp.target == tgt]
    if len(c):
        st.markdown("**Backtest accuracy by method** (time-based rolling origins; last origin = holdout; lower WAPE is better)")
        st.dataframe(c.drop(columns=["data_status"], errors="ignore").round(3), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**3. Repair cycle-time prediction** (collision, approval -> delivery; test = approvals in 2026)")
        st.dataframe(table("cycle_time_model_evaluation").drop(columns=["data_status"], errors="ignore").round(2), use_container_width=True, hide_index=True)
        imp = table("cycle_time_feature_importance")
        if len(imp):
            show(px.bar(imp.sort_values("importance"), x="importance", y=imp.columns[0], orientation="h", title="Feature importance (XGBoost)", labels={imp.columns[0]: ""}), 330)
    with c2:
        st.markdown("**6. Expected cash collections** (insurer & fleet receivables collected in the next 30 days)")
        st.dataframe(table("collections_model_evaluation").drop(columns=["data_status"], errors="ignore").round(3), use_container_width=True, hide_index=True)
        bt = table("collections_backtest")
        fig = go.Figure([go.Scatter(x=pd.to_datetime(bt.origin), y=bt.actual_collected_30d, name="Actual", line=dict(color=TOT, width=3)),
                         go.Scatter(x=pd.to_datetime(bt.origin), y=bt.model_predicted, name="Model", line=dict(color=FIN[0], width=2)),
                         go.Scatter(x=pd.to_datetime(bt.origin), y=bt.baseline_avg_rate, name="Baseline (average rate)", line=dict(color=FIN[3], width=2, dash="dot"))])
        fig.update_layout(title="Backtest: next-30-day collections at each month end", yaxis_tickprefix="$")
        show(fig, 330)
    st.markdown("**Demand vs technician capacity in the integrated forecast (Base scenario, billed hours)**")
    res = F.run(F.SCENARIOS["Base"], fbase())
    mo = pd.to_datetime(res.columns[1:])
    fig = go.Figure([go.Bar(x=mo, y=res.loc["coll_dem"].iloc[1:], name="Collision demand", marker_color=FIN[0]),
                     go.Scatter(x=mo, y=res.loc["coll_cap"].iloc[1:], name="Regular capacity", line=dict(color=BRAND["bad"], width=2)),
                     go.Scatter(x=mo, y=res.loc["coll_cap"].iloc[1:] + res.loc["coll_ot_cap"].iloc[1:], name="Capacity incl. overtime", line=dict(color=BRAND["bad"], width=2, dash="dot"))])
    fig.update_layout(title="Collision: FORECAST demand vs capacity")
    show(fig, 340)
    download(fc, "forecast_next_12_months")
    download_file(FIN_OUT / "Prairie_Auto_Care_Integrated_Financial_Model.xlsx", "Download integrated three-statement model (Excel, live formulas)")


def p_sim():
    st.subheader("Financial scenario simulator (12-month integrated forecast)")
    st.caption("Every slider feeds the same formula engine as the Excel model; revenue, profit, cash and working capital stay reconciled. Collision and mechanical revenue are "
               "capacity-constrained: more efficiency or more technicians only add sales when demand exceeds capacity. Illustrative only.")
    b = fbase()
    preset = st.selectbox("Start from", ["Base", "Conservative", "Optimistic"])
    p0 = F.SCENARIOS[preset]
    c1, c2, c3 = st.columns(3)
    with c1:
        eff = st.slider("Technician efficiency change %", -20.0, 20.0, p0.eff_change * 100, 1.0) / 100
        parts = st.slider("Parts procurement cost change %", -10.0, 10.0, p0.parts_cost_change * 100, 0.5) / 100
        cyc = st.slider("Repair cycle-time change %", -30.0, 20.0, p0.cycle_change * 100, 1.0) / 100
        appt = st.slider("Appointment volume change %", -20.0, 25.0, p0.appt_change * 100, 1.0) / 100
    with c2:
        gm = st.slider("Gross-margin improvement % (relative)", -5.0, 10.0, p0.margin_change * 100, 0.5) / 100
        col = st.slider("Receivable collection-delay change %", -40.0, 30.0, p0.collect_change * 100, 1.0) / 100
        hires = st.slider("Additional collision technicians (from Dec-2026)", 0, 4, int(p0.hires), 1)
    with c3:
        exp = st.slider("Detailing & paint-protection expansion %", 0.0, 50.0, p0.expansion * 100, 5.0) / 100
        opx = st.slider("Operating expense change %", -15.0, 15.0, p0.opex_change * 100, 0.5) / 100
        rate = st.slider("Prime-rate change (bps)", -200, 300, int(p0.rate_change * 10000), 25) / 10000
    sc = replace(F.SCENARIOS["Base"], eff_change=eff, parts_cost_change=parts, cycle_change=cyc, appt_change=appt, margin_change=gm, collect_change=col, hires=float(hires),
                 expansion=exp, opex_change=opx, rate_change=rate)
    res, base = F.run(sc, b), F.run(F.SCENARIOS["Base"], b)
    r, r0 = F.summary(res), F.summary(base)
    kpis([("Net revenue", money(r["net_revenue"]), f"{r['net_revenue'] - r0['net_revenue']:+,.0f} vs Base", r["net_revenue"] >= r0["net_revenue"]),
          ("Gross profit", money(r["gross_profit"]), f"GM {r['gross_margin_pct']:.1f}%", r["gross_profit"] >= r0["gross_profit"]),
          ("Operating profit", money(r["operating_profit"]), f"{r['operating_profit'] - r0['operating_profit']:+,.0f}", r["operating_profit"] >= r0["operating_profit"]),
          ("Operating cash flow", money(r["cfo"]), f"{r['cfo'] - r0['cfo']:+,.0f}", r["cfo"] >= r0["cfo"]),
          ("Closing cash", money(r["closing_cash"]), f"{r['closing_cash'] - r0['closing_cash']:+,.0f}", None),
          ("Working capital", money(r["closing_working_capital"]), f"{r['closing_working_capital'] - r0['closing_working_capital']:+,.0f}", None),
          ("Collision hours delivered", f"{r['collision_hours']:,.0f}", f"{r['collision_hours'] - r0['collision_hours']:+,.0f} h", None),
          ("Collision overtime", f"{r['collision_overtime_hours']:,.0f} h", f"{r['collision_overtime_hours'] - r0['collision_overtime_hours']:+,.0f} h", r["collision_overtime_hours"] <= r0["collision_overtime_hours"]),
          ("Net income", money(r["net_income"]), f"{r['net_income'] - r0['net_income']:+,.0f}", r["net_income"] >= r0["net_income"])], per_row=5)
    fm = pd.to_datetime(res.columns[1:])
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure([go.Bar(x=fm, y=base.loc["ebit"].iloc[1:], name="Base", marker_color=FIN[0]), go.Bar(x=fm, y=res.loc["ebit"].iloc[1:], name="Scenario", marker_color=FIN[1])])
        fig.update_layout(barmode="group", title="FORECAST monthly operating profit", yaxis_tickprefix="$")
        show(fig, 340)
    with c2:
        fig = go.Figure([go.Scatter(x=fm, y=base.loc["cash"].iloc[1:], name="Base", line=dict(color=FIN[0], width=3)),
                         go.Scatter(x=fm, y=res.loc["cash"].iloc[1:], name="Scenario", line=dict(color=FIN[1], width=3))])
        fig.update_layout(title="FORECAST month-end cash", yaxis_tickprefix="$")
        show(fig, 340)
    fig = go.Figure([go.Bar(x=fm, y=res.loc["coll_dem"].iloc[1:], name="Demand (incl. volume change)", marker_color=FIN[0]),
                     go.Scatter(x=fm, y=res.loc["coll_hours"].iloc[1:], name="Hours delivered", line=dict(color=FIN[1], width=3)),
                     go.Scatter(x=fm, y=res.loc["coll_cap"].iloc[1:], name="Regular capacity", line=dict(color=BRAND["bad"], width=2, dash="dot"))])
    fig.update_layout(title="Collision capacity check (billed hours) - why efficiency alone may not raise sales")
    show(fig, 320)
    st.markdown("**Required scenarios (each lever alone vs Base)**")
    sens = table("fin_forecast_sensitivity")
    st.dataframe(sens[["scenario", "delta_net_revenue", "delta_gross_profit", "delta_operating_profit", "delta_cfo", "delta_working_capital", "delta_collision_hours",
                       "delta_overtime_hours"]].round(0), use_container_width=True, hide_index=True)
    download(sens, "scenario_sensitivity")
    with st.expander("Formulas and assumptions"):
        st.dataframe(pd.DataFrame([(k, lab, tpl) for k, lab, _, tpl, _ in F.ROWS], columns=["key", "line", "formula template"]), use_container_width=True, hide_index=True, height=300)
        st.json({k: round(v, 4) for k, v in b["A"].items()})
    st.warning("Scenario results are illustrative estimates for a fictional business on synthetic data, not forecasts of any real company's results.")


{PAGES[0]: p_exec, PAGES[1]: p_profit, PAGES[2]: p_tech, PAGES[3]: p_cycle, PAGES[4]: p_parts, PAGES[5]: p_supplier, PAGES[6]: p_claims, PAGES[7]: p_customer,
 PAGES[8]: p_branch, PAGES[9]: p_is, PAGES[10]: p_bs, PAGES[11]: p_cf, PAGES[12]: p_ratios, PAGES[13]: p_forecast, PAGES[14]: p_sim}[page]()

st.markdown(f"<div style='text-align:center;color:{BRAND['subtle']};font-size:.75rem;margin-top:30px'>{APP_BANNER} | "
            "Prairie Auto Care Group is a fictional business; no endorsement by or relationship with any real company is implied.</div>", unsafe_allow_html=True)
