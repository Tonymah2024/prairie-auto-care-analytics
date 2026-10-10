"""Phase 9 - predictive analytics on the SYNTHETIC data. Writes the 12-month forecasts used by the financial model, every
backtest, the cycle-time and collections model evaluations and the parts reorder recommendations.

  1. Monthly service revenue (total and by line)            - revenue at delivery (gross of discounts)
  2. Repair-order volume & billed-hours demand              - ROs and billed hours by inquiry month (demand arrival)
  3. Repair cycle-time prediction                           - approval-to-delivery days, predicted at approval (collision)
  4. Parts demand                                           - monthly stocked-part units by category; seasonal reorder points
  5. Technician capacity                                    - available hours (headcount plan x seasonal hours per technician)
  6. Expected cash collections                              - insurer & fleet receivable run-off from empirical payment-lag curves

Model performance on synthetic data does NOT establish real-world prediction accuracy.
"""
from __future__ import annotations

import json

import holidays
import numpy as np
import pandas as pd

from src.config import END, MODELS, TABLES
from src.engineering.load_db import read_all
from src.models import ts

DISCLAIMER = "Model performance measured on SYNTHETIC data; it does not establish real-world prediction accuracy."
H = 12
FC_IDX = pd.period_range("2026-10", periods=H, freq="M")


def monthly(s: pd.Series, start, end=END):
    return s.groupby(s.index.to_period("M")).sum().reindex(pd.period_range(start, end, freq="M"), fill_value=0.0)


def gross(inv):
    f = inv.groupby("ro_id").first()
    return (f.labour_cad + f.parts_cad + f.paint_materials_cad + f.sublet_cad + f.fees_cad).rename("gross")


# ----------------------------------------------------------------------------------------------- 1 & 2: revenue, volume, hours
def series(T):
    ro, inv = T["repair_orders"], T["customer_invoices"]
    g = gross(inv)
    fi = inv.groupby("ro_id").invoice_date.first()
    rv = pd.DataFrame({"gross": g, "date": fi}).join(ro.set_index("ro_id")[["service_line"]])
    S = {"revenue_total": monthly(rv.set_index("date").gross, "2024-01")}
    for line, key in [("Collision repair", "collision"), ("Mechanical service", "mechanical"), ("Detailing", "detailing"), ("Glass repair", "glass"), ("Other services", "other")]:
        x = rv[rv.service_line == line]
        S[f"revenue_{key}"] = monthly(x.set_index("date").gross, "2024-01")
    dem = ro[(ro.payer_type != "Warranty (internal)") & ~ro.status.isin(["Estimate declined", "Repair declined (cash settlement)", "Total loss", "Estimate declined (diagnostic fee)"])]
    dem = dem.set_index("inquiry_date")
    for line, key in [("Collision repair", "collision"), ("Mechanical service", "mechanical"), ("Detailing", "detailing"), ("Glass repair", "glass"), ("Other services", "other")]:
        S[f"ros_{key}"] = monthly(dem[dem.service_line == line].ro_id.map(lambda _: 1.0), "2023-10")
    S["billed_hours_collision"] = monthly(dem[dem.service_line == "Collision repair"][["billed_body_hours", "billed_paint_hours"]].sum(axis=1), "2023-10")
    S["billed_hours_mechanical"] = monthly(dem[dem.service_line == "Mechanical service"].billed_mech_hours, "2023-10")
    return S


# ----------------------------------------------------------------------------------------------- 5: technician capacity
def workdays(month: pd.Period, sat=False):
    ab = holidays.country_holidays("CA", subdiv="AB", years=[month.year])
    d = pd.date_range(month.start_time, month.end_time.normalize())
    wk = sum(1 for x in d if x.weekday() < 5 and x not in ab)
    return wk


def capacity(T):
    """Available hours by technician group. Model: active headcount at the origin x seasonal available hours per technician-workday x
    workdays in the month (Alberta holidays). Baselines: same month last year; mean of the last 3 months."""
    ts_ = T["technician_timesheets"].merge(T["technicians"][["tech_id", "op_groups", "hire_date", "termination_date"]], on="tech_id")
    ts_["grp"] = np.select([ts_.op_groups.str.contains("BODY|PAINT"), ts_.op_groups.str.startswith("MECH")], ["collision", "mechanical"], "other")
    ts_["m"] = ts_.work_date.dt.to_period("M")
    out, evals, preds = {}, [], []
    tech = T["technicians"]
    for grp in ["collision", "mechanical"]:
        x = ts_[ts_.grp == grp]
        y = x.groupby("m").available_hours.sum().reindex(pd.period_range("2024-01", END, freq="M"), fill_value=0.0)
        # per technician-workday available hours, by calendar month (PTO seasonality)
        per = x[x.scheduled_hours == 8].groupby(["m"]).agg(av=("available_hours", "sum"), n=("timesheet_id", "count"))
        per["rate"] = per.av / per.n
        sat = x[x.scheduled_hours == 3].groupby("m").available_hours.sum()

        def predict(origin, months):
            o = pd.Period(origin, "M")
            hist = per[per.index <= o]
            mrate = hist.groupby(hist.index.month).rate.mean()
            at = o.end_time.normalize()
            ids = set(x.tech_id)
            hc = tech[tech.tech_id.isin(ids) & (tech.hire_date <= at) & (tech.termination_date.isna() | (tech.termination_date > at))]
            n = len(hc)
            satm = sat[sat.index <= o].iloc[-6:].mean() if len(sat[sat.index <= o]) else 0.0
            return np.array([n * workdays(m) * mrate.get(m.month, hist.rate.mean()) + satm for m in months])

        for k, o in enumerate(["2025-09", "2025-12", "2026-03"]):
            te = y[y.index > pd.Period(o, "M")].iloc[:6]
            tr = y[y.index <= pd.Period(o, "M")]
            cands = {"Headcount x seasonal hours (model)": predict(o, te.index), "Same month last year": np.array([tr.get(m - 12, tr.iloc[-1]) for m in te.index]),
                     "Mean of last 3 months": np.repeat(tr.iloc[-3:].mean(), len(te))}
            for mth, p in cands.items():
                evals.append(dict(target=f"tech_available_hours_{grp}", origin=o, holdout=int(k == 2), method=mth, **ts.metrics(te.values, p)))
                preds += [dict(target=f"tech_available_hours_{grp}", origin=o, method=mth, month=str(mm), actual=float(a), forecast=float(f)) for mm, a, f in zip(te.index, te.values, p)]
        f = predict(END[:7], FC_IDX)
        out[f"tech_available_hours_{grp}"] = pd.DataFrame({"target": f"tech_available_hours_{grp}", "month": FC_IDX.to_timestamp(), "forecast": f, "lower80": f * .95,
                                                           "upper80": f * 1.03, "model": "Headcount x seasonal hours (model)"})
    return out, pd.DataFrame(evals), pd.DataFrame(preds)


# ----------------------------------------------------------------------------------------------- 3: cycle time
def cycle_time(T):
    from sklearn.linear_model import Ridge
    from xgboost import XGBRegressor
    ro = T["repair_orders"]
    po = T["supplier_purchase_orders"]
    c = ro[ro.service_type.isin(["COL_MIN", "COL_MOD", "COL_MAJ", "REFIN"]) & (ro.payer_type != "Warranty (internal)") & ro.approval_date.notna()].copy()
    so = po[po.po_type == "Special order"]
    agg = so[so.supplement == 0].groupby("ro_id").agg(n_lines=("po_line_id", "count"), lux=("supplier_id", lambda s: int((s == "SUP-08").any())),
                                                      aftermarket=("supplier_id", lambda s: int((s == "SUP-02").any())))
    c = c.join(agg, on="ro_id")
    c[["n_lines", "lux", "aftermarket"]] = c[["n_lines", "lux", "aftermarket"]].fillna(0)
    veh = T["vehicles"].set_index("vehicle_id")
    c["vehicle_category"] = c.vehicle_id.map(veh.vehicle_category)
    c["adas"] = c.vehicle_id.map(veh.adas_equipped)
    ins = T["insurers"].set_index("insurer_id").insurer_category
    c["payer"] = np.where(c.payer_type == "Insurance", c.insurer_id.map(ins).str.split(" ").str[0], c.payer_type)
    # shop load at approval: open collision ROs at the performing branch (known at approval time - no leakage)
    c = c.sort_values("approval_date")
    load = []
    st = ro[ro.service_type.isin(["COL_MIN", "COL_MOD", "COL_MAJ", "REFIN"])]
    for b, g in c.groupby("performing_branch_id"):
        sb = st[st.performing_branch_id == b]
        starts = np.sort(sb.approval_date.dropna().values)
        ends = np.sort(sb.delivered_date.dropna().values)
        for i, d in zip(g.index, g.approval_date.values):
            load.append((i, np.searchsorted(starts, d, "right") - np.searchsorted(ends, d, "right")))
    c["open_jobs_at_approval"] = pd.Series(dict(load))
    c["month"] = c.approval_date.dt.month
    c["target"] = (c.delivered_date - c.approval_date).dt.days
    feats_num = ["billed_labour_hours", "est_total_cad", "n_lines", "lux", "aftermarket", "adas", "towed_in", "open_jobs_at_approval", "month", "hail_related"]
    feats_cat = ["service_type", "payer", "vehicle_category", "performing_branch_id"]
    c["billed_labour_hours"] = c.est_labour_hours                                  # at approval only the estimate's hours are known
    done = c[c.target.notna() & (c.pre_period == 0)]
    X = pd.get_dummies(done[feats_num + feats_cat], columns=feats_cat, dtype=float)
    cut = pd.Timestamp("2026-01-01")
    tr, te = done.approval_date < cut, done.approval_date >= cut
    y = done.target.values
    base = done[tr].groupby("service_type").target.median()
    pred = {"Baseline: median by service type": done[te].service_type.map(base).values}
    rid = Ridge(alpha=3.0).fit(X[tr], y[tr])
    pred["Ridge regression"] = rid.predict(X[te])
    xg = XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.85, colsample_bytree=0.8, random_state=7).fit(X[tr], y[tr])
    pred["XGBoost"] = xg.predict(X[te])
    rows = []
    yt = y[te]
    for k, p in pred.items():
        rows.append(dict(model=k, MAE_days=float(np.abs(yt - p).mean()), RMSE_days=float(np.sqrt(((yt - p) ** 2).mean())),
                         within_3_days=float((np.abs(yt - p) <= 3).mean()), R2=float(1 - ((yt - p) ** 2).sum() / ((yt - yt.mean()) ** 2).sum()), n_test=int(te.sum())))
    ev = pd.DataFrame(rows)
    best = ev.sort_values("MAE_days").iloc[0].model
    imp = pd.Series(xg.feature_importances_, index=X.columns).sort_values(ascending=False).head(12)
    # residual-based 80% band from the test set (for estimated completion dates)
    res = yt - (pred[best] if best in pred else pred["XGBoost"])
    q10, q90 = np.quantile(res, [.1, .9])
    # estimated completion dates for open collision ROs (refit on all completed jobs)
    final = XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.85, colsample_bytree=0.8, random_state=7).fit(X, y) if best == "XGBoost" else \
        Ridge(alpha=3.0).fit(X, y)
    op = c[c.delivered_date.isna() & ~c.status.isin(["Estimate declined", "Repair declined (cash settlement)", "Total loss"])].copy()
    if len(op):
        Xo = pd.get_dummies(op[feats_num + feats_cat], columns=feats_cat, dtype=float).reindex(columns=X.columns, fill_value=0.0)
        p = final.predict(Xo) if best != "Baseline: median by service type" else op.service_type.map(base).values
        op["predicted_days_from_approval"] = np.round(p, 1)
        op["estimated_completion_date"] = op.approval_date + pd.to_timedelta(np.maximum(p, (pd.Timestamp(END) - op.approval_date).dt.days + 1), unit="D")
        op["completion_p10"] = op.approval_date + pd.to_timedelta(np.maximum(p + q10, (pd.Timestamp(END) - op.approval_date).dt.days + 1), unit="D")
        op["completion_p90"] = op.approval_date + pd.to_timedelta(np.maximum(p + q90, (pd.Timestamp(END) - op.approval_date).dt.days + 1), unit="D")
    ecd = op[["ro_id", "branch_id", "performing_branch_id", "service_type", "status", "approval_date", "promised_date", "predicted_days_from_approval",
              "estimated_completion_date", "completion_p10", "completion_p90"]] if len(op) else pd.DataFrame()
    tp = done[te][["ro_id", "service_type", "approval_date", "target"]].assign(predicted=pred[best] if best in pred else pred["XGBoost"])
    return ev, best, imp, ecd, tp


# ----------------------------------------------------------------------------------------------- 4: parts demand + reorder points
def parts(T):
    mv, cat = T["parts_inventory_movements"], T["parts_catalogue"].set_index("part_id")
    iss = mv[(mv.movement_type == "ISSUE_TO_RO") & (mv.inventory_state == "stock") & (mv.movement_date >= "2024-01-01")].copy()
    iss["qty"] = -iss.quantity
    iss["kind"] = iss.part_id.map(cat.part_category)
    fcs, evs, prs, best = [], [], [], {}
    for kind, g in iss.groupby("kind"):
        y = monthly(g.set_index("movement_date").qty, "2024-01")
        if y.sum() < 50:
            continue
        fc, ev, pr, b = ts.forecast_series(f"parts_units_{kind}", y, ["2025-12", "2026-03"], 6, H, ["Seasonal naive", "Recent level x seasonal index", "Holt-Winters (damped)", "XGBoost"])
        fcs.append(fc), evs.append(ev), prs.append(pr)
        best[kind] = b
    # seasonal reorder points per branch-SKU: next-month forecast share x category forecast; safety stock by ABC class
    pol = T["stock_policy_current"]
    sup = T["suppliers"].set_index("supplier_id")
    dem12 = iss[iss.movement_date >= pd.Timestamp(END) - pd.Timedelta(days=365)]
    sku = dem12.groupby(["branch_id", "part_id"]).agg(units_12m=("qty", "sum"), value_12m=("value_cad", lambda v: -v.sum()))
    d = iss.groupby([iss.branch_id, iss.part_id, iss.movement_date.dt.to_period("W")]).qty.sum()
    wk_sd = d.groupby(level=[0, 1]).std().rename("weekly_sd")
    sku = sku.join(wk_sd).fillna({"weekly_sd": 0})
    sku["abc"] = "C"
    for b, g in sku.groupby(level=0):
        s = g.value_12m.sort_values(ascending=False)
        cum = s.cumsum() / s.sum()
        sku.loc[cum[cum <= .8].index, "abc"] = "A"
        sku.loc[cum[(cum > .8) & (cum <= .95)].index, "abc"] = "B"
    fc_all = pd.concat(fcs)
    kshare = {}
    for kind, g in iss.groupby("kind"):
        f = fc_all[fc_all.target == f"parts_units_{kind}"]
        if len(f):
            last12 = monthly(g.set_index("movement_date").qty, "2024-01").iloc[-12:].sum()
            kshare[kind] = (f.forecast.values[:3].mean() * 12) / max(last12, 1)          # next-quarter demand rate vs last 12 months
    rows = []
    for (b, p), r in sku.iterrows():
        kind = cat.at[p, "part_category"]
        lt = sup.at[cat.at[p, "default_supplier_id"], "lead_time_mean_days"] / 5
        wk = r.units_12m / 52 * kshare.get(kind, 1.0)
        z = {"A": 1.65, "B": 1.28, "C": 1.04}[r.abc]
        ss = z * r.weekly_sd * np.sqrt(lt + 1)
        rop = int(np.ceil(wk * (lt + 1) + ss))
        cur = pol[(pol.branch_id == b) & (pol.part_id == p)]
        rows.append(dict(branch_id=b, part_id=p, description=cat.at[p, "description"], part_category=kind, abc_class=r.abc, units_last_12m=r.units_12m,
                         forecast_weekly_demand_next_qtr=round(wk, 2), lead_time_weeks=round(lt, 2), service_level={"A": .95, "B": .90, "C": .85}[r.abc],
                         safety_stock=round(ss, 1), recommended_reorder_point=rop, recommended_order_up_to=int(rop + np.ceil(wk * 2)),
                         current_reorder_point=int(cur.reorder_point.iloc[0]) if len(cur) else None, current_order_up_to=int(cur.order_up_to.iloc[0]) if len(cur) else None))
    return fc_all, pd.concat(evs), pd.concat(prs), best, pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------- 6: cash collections
def collections(T):
    """Probability that an open insurer / fleet invoice is paid within d days given its age, from empirical payment-lag curves fitted on
    invoices paid BEFORE the origin. Backtest: predicted vs actual cash collected in the 30 days after each month-end origin."""
    inv, pay = T["customer_invoices"], T["payments"]
    x = inv[inv.bill_to_type.isin(["Insurer", "Fleet account"]) & (inv.total_cad > 0)][["invoice_id", "invoice_date", "total_cad", "bill_to_type", "bill_to_id"]]
    p = pay.groupby("invoice_id").agg(paid=("payment_date", "max"), cash=("amount_cad", "sum"))
    x = x.join(p, on="invoice_id")
    x["lag"] = (x.paid - x.invoice_date).dt.days
    origins = pd.period_range("2024-09", "2026-08", freq="M")
    rows = []
    for o in origins:
        at = o.end_time.normalize()
        hist = x[x.paid <= at]
        op = x[(x.invoice_date <= at) & ~(x.paid <= at)]
        nxt = at + pd.Timedelta(days=30)
        actual = op[(op.paid > at) & (op.paid <= nxt)].cash.sum()
        rate_by = {}
        pred = 0.0
        for r in op.itertuples():
            age = (at - r.invoice_date).days
            key = r.bill_to_id
            hh = hist[hist.bill_to_id == key] if (hist.bill_to_id == key).sum() >= 30 else hist[hist.bill_to_type == r.bill_to_type]
            surv = hh[hh.lag > age]
            prob = ((surv.lag <= age + 30).mean()) if len(surv) else 0.9
            pred += prob * r.total_cad * 0.995
        avg_rate = (hist.lag <= 30).mean()
        rows.append(dict(origin=str(o), open_receivables=op.total_cad.sum(), actual_collected_30d=actual, model_predicted=pred,
                         baseline_avg_rate=op.total_cad.sum() * avg_rate, baseline_terms_30d=op[(at - op.invoice_date).dt.days <= 30].total_cad.sum()))
    bt = pd.DataFrame(rows)
    ev = []
    for k, lab in [("model_predicted", "Payment-lag curves by insurer (model)"), ("baseline_avg_rate", "Average 30-day collection rate (baseline)"),
                   ("baseline_terms_30d", "Terms-based: everything due by 30 days (baseline)")]:
        ev.append(dict(target="cash_collections_30d", method=lab, **ts.metrics(bt.actual_collected_30d, bt[k])))
    # 12-month cash-collections forecast: run-off of open AR + collections on forecast revenue (customer share at pickup, insurer/fleet by lag profile)
    at = pd.Timestamp(END)
    hist = x[x.paid <= at]
    lagp = hist.groupby(pd.cut(hist.lag, [-1, 30, 60, 90, 120, 10_000], labels=[0, 1, 2, 3, 4], ordered=False), observed=False).cash.sum()
    lagp = (lagp / lagp.sum()).reindex([0, 1, 2, 3, 4], fill_value=0).values
    op = x[(x.invoice_date <= at) & ~(x.paid <= at)]
    runoff = np.zeros(H)
    for r in op.itertuples():
        age = (at - r.invoice_date).days
        hh = hist[hist.bill_to_type == r.bill_to_type]
        surv = hh[hh.lag > age]
        for j in range(H):
            pr = ((surv.lag > age + 30 * j) & (surv.lag <= age + 30 * (j + 1))).mean() if len(surv) else (1.0 if j == 0 else 0.0)
            runoff[j] += pr * r.total_cad
    return bt, pd.DataFrame(ev), runoff, lagp, x


def run():
    T = read_all()
    S = series(T)
    fcs, evs, prs, chosen = [], [], [], {}
    for name, y in S.items():
        origins = ["2025-12", "2026-03"] if name.startswith("revenue") else ["2025-09", "2025-12", "2026-03"]
        fc, ev, pr, best = ts.forecast_series(name, y, origins)
        fcs.append(fc), evs.append(ev), prs.append(pr)
        chosen[name] = best
    cap, cap_ev, cap_pr = capacity(T)
    fcs += list(cap.values())
    evs.append(cap_ev), prs.append(cap_pr)
    for k in cap:
        chosen[k] = "Headcount x seasonal hours (model)"
    pf, pe, pp, pbest, rop = parts(T)
    fcs.append(pf), evs.append(pe), prs.append(pp)
    ct_ev, ct_best, ct_imp, ecd, ct_test = cycle_time(T)
    bt, col_ev, runoff, lagp, xinv = collections(T)
    fc = pd.concat(fcs, ignore_index=True)
    # cash collections: pickup receipts + insurer/fleet run-off of open AR + collections on forecast revenue (lag profile)
    inv = T["customer_invoices"]
    ttm = inv[inv.invoice_date > pd.Timestamp(END) - pd.Timedelta(days=365)]
    share_cust = ttm[ttm.bill_to_type.str.startswith("Customer")].total_cad.sum() / ttm.total_cad.sum()
    rev = fc[fc.target == "revenue_total"].forecast.values * 1.05
    later = np.convolve(rev * (1 - share_cust), lagp)[:H]
    cash = rev * share_cust + later + runoff
    fc = pd.concat([fc, pd.DataFrame({"target": "cash_collections", "month": FC_IDX.to_timestamp(), "forecast": cash, "lower80": cash * .93, "upper80": cash * 1.06,
                                      "model": "Pickup receipts + payment-lag curves (model)"})], ignore_index=True)
    fc["data_status"] = "FORECAST (SYNTHETIC)"
    fc.to_csv(TABLES / "forecast_next_12_months.csv", index=False)
    ev = pd.concat(evs, ignore_index=True)
    ev.to_csv(TABLES / "forecast_model_comparison.csv", index=False)
    pd.concat(prs, ignore_index=True).to_csv(TABLES / "forecast_backtest_predictions.csv", index=False)
    hist = pd.concat([y.rename("actual").to_frame().assign(target=n) for n, y in S.items()]).reset_index().rename(columns={"index": "month"})
    hist["month"] = hist.month.astype(str)
    hist.to_csv(TABLES / "forecast_history.csv", index=False)
    ct_ev.to_csv(TABLES / "cycle_time_model_evaluation.csv", index=False)
    ct_imp.rename("importance").to_frame().to_csv(TABLES / "cycle_time_feature_importance.csv")
    ecd.to_csv(TABLES / "estimated_completion_dates_open_ros.csv", index=False)
    ct_test.to_csv(TABLES / "cycle_time_test_predictions.csv", index=False)
    bt.to_csv(TABLES / "collections_backtest.csv", index=False)
    col_ev.to_csv(TABLES / "collections_model_evaluation.csv", index=False)
    rop.to_csv(TABLES / "reorder_point_recommendations.csv", index=False)
    res = {"disclaimer": DISCLAIMER, "chosen_models": chosen, "parts_models": pbest, "cycle_time_best": ct_best,
           "cycle_time": ct_ev.to_dict("records"), "collections": col_ev.to_dict("records"),
           "holdout_wape": ev[ev.holdout == 1].pivot_table(index="target", columns="method", values="WAPE").round(4).to_dict("index")}
    (TABLES / "model_results.json").write_text(json.dumps(res, indent=1, default=str))
    (MODELS / "model_card.json").write_text(json.dumps({"models": list(chosen.items()), "disclaimer": DISCLAIMER}, indent=1))
    return res


if __name__ == "__main__":
    import time
    t = time.time()
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k in ("chosen_models", "cycle_time_best", "cycle_time", "collections")}, indent=1, default=str)[:4000])
    print(f"{time.time() - t:.0f}s")
