"""Monthly time-series forecasting toolkit with leakage-safe, rolling-origin evaluation (models 1, 2, 4 and 5).

Methods compared on every target: seasonal naive (baseline), recent level x seasonal index (robust to a completed ramp-up such as a
new branch), Holt-Winters (damped trend, phi = 0.8, additive seasonality on logs),
SARIMAX(1,0,0)(0,1,0,12) with drift on logs, and XGBoost on calendar + lag features (recursive). Each origin trains ONLY on
months up to the origin. Performance is measured on SYNTHETIC data and does not establish real-world prediction accuracy.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
METHODS = ["Seasonal naive", "Recent level x seasonal index", "Holt-Winters (damped)", "SARIMAX", "XGBoost"]
Z80 = 1.2816


def _log(y):
    return np.log(np.maximum(y, 1.0))


def fit_predict(method, y: pd.Series, h: int):
    """y: monthly series (PeriodIndex). Returns (mean, lower80, upper80) arrays of length h."""
    idx = pd.period_range(y.index[-1] + 1, periods=h, freq="M")
    if method == "Seasonal naive":
        last = y.iloc[-12:].values
        m = np.array([last[i % 12] for i in range(h)])
        resid = (y.values[12:] - y.values[:-12]) if len(y) > 12 else np.array([0.0])
        s = np.std(resid) if len(resid) > 1 else 0.0
        k = np.sqrt(np.floor(np.arange(h) / 12) + 1)
        return m, m - Z80 * s * k, m + Z80 * s * k
    if method == "Recent level x seasonal index":
        v = y.values.astype(float)
        ma = pd.Series(v).rolling(12, center=True).mean().rolling(2).mean().shift(-1).values
        ratio = pd.Series(v / ma, index=y.index).dropna()
        si = ratio.groupby(ratio.index.month).mean()
        si = (si / si.mean()).reindex(range(1, 13)).fillna(1.0)
        ds = v / si.reindex(y.index.month).values
        level = ds[-3:].mean()
        m = np.array([level * si[p.month] for p in idx])
        s = np.std(ds[-12:] / ds[-12:].mean()) * level
        k = np.sqrt(1 + np.arange(h) / 3)
        return m, m - Z80 * s * k, m + Z80 * s * k
    if method == "Holt-Winters (damped)":
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        mod = ExponentialSmoothing(_log(y.values), trend="add", damped_trend=True, seasonal="add", seasonal_periods=12,
                                   initialization_method="estimated").fit(optimized=True, damping_trend=0.8)
        f = mod.forecast(h)
        s = np.std(mod.resid)
        k = np.sqrt(1 + np.arange(h) * 0.15)
        return np.exp(f), np.exp(f - Z80 * s * k), np.exp(f + Z80 * s * k)
    if method == "SARIMAX":
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        mod = SARIMAX(_log(y.values), order=(1, 0, 0), seasonal_order=(0, 1, 0, 12), trend="c").fit(disp=False)
        fc = mod.get_forecast(h)
        ci = fc.conf_int(alpha=0.2)
        return np.exp(fc.predicted_mean), np.exp(ci[:, 0]), np.exp(ci[:, 1])
    if method == "XGBoost":
        from xgboost import XGBRegressor
        v = list(y.values)
        X, t = [], []
        for i in range(12, len(v)):
            X.append([v[i - 12], v[i - 1], v[i - 2], v[i - 3], np.sin(2 * np.pi * y.index[i].month / 12), np.cos(2 * np.pi * y.index[i].month / 12), i])
            t.append(v[i])
        mdl = XGBRegressor(n_estimators=250, max_depth=2, learning_rate=0.06, subsample=0.9, random_state=7).fit(np.array(X), np.array(t))
        res = np.array(t) - mdl.predict(np.array(X))
        out = []
        for j in range(h):
            i = len(v)
            row = [v[i - 12], v[i - 1], v[i - 2], v[i - 3], np.sin(2 * np.pi * idx[j].month / 12), np.cos(2 * np.pi * idx[j].month / 12), i]
            p = float(mdl.predict(np.array([row]))[0])
            out.append(p)
            v.append(p)
        m = np.array(out)
        s = np.std(res) * 1.6                    # in-sample residuals understate out-of-sample error for trees
        return m, m - Z80 * s, m + Z80 * s
    raise ValueError(method)


def metrics(actual, pred, lo=None, hi=None):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    out = {"WAPE": float(np.abs(a - p).sum() / max(np.abs(a).sum(), 1e-9)), "MAE": float(np.abs(a - p).mean()), "RMSE": float(np.sqrt(((a - p) ** 2).mean())),
           "bias_pct": float((p.sum() - a.sum()) / max(a.sum(), 1e-9) * 100)}
    if lo is not None:
        out["PI80_coverage"] = float(((a >= lo) & (a <= hi)).mean())
    return out


def evaluate(y: pd.Series, origins, h=6, methods=METHODS):
    """Rolling-origin backtest. The last origin is the HOLDOUT (final h months)."""
    rows, preds = [], []
    for k, o in enumerate(origins):
        tr = y[y.index <= pd.Period(o, "M")]
        te = y[(y.index > pd.Period(o, "M"))].iloc[:h]
        if len(te) == 0:
            continue
        for mth in methods:
            try:
                m, lo, hi = fit_predict(mth, tr, len(te))
            except Exception:
                continue
            r = metrics(te.values, m, lo, hi)
            rows.append(dict(origin=str(o), holdout=int(k == len(origins) - 1), method=mth, **r))
            preds += [dict(origin=str(o), method=mth, month=str(p), actual=float(a), forecast=float(f), lower80=float(l), upper80=float(u))
                      for p, a, f, l, u in zip(te.index, te.values, m, lo, hi)]
    return pd.DataFrame(rows), pd.DataFrame(preds)


def choose(ev: pd.DataFrame):
    """Select by the average of holdout WAPE and mean WAPE over all origins (stable, not holdout-lucky)."""
    hold = ev[ev.holdout == 1].set_index("method").WAPE
    allo = ev.groupby("method").WAPE.mean()
    score = (hold + allo) / 2
    return score.idxmin(), score


BAND = (0.85, 1.25)      # reasonableness guard: 12-month forecast total vs trailing 12 months


def forecast_series(name, y, origins, h_eval=6, h=12, methods=METHODS):
    """Pick the best backtest score among methods whose 12-month total stays within BAND of the trailing 12 months
    (a model that extrapolates a completed ramp-up or a one-off hail surge is passed over); fall back to the best score."""
    ev, pr = evaluate(y, origins, h_eval, methods)
    best, score = choose(ev)
    ttm = y.iloc[-12:].sum()
    fits = {}
    for mth in score.sort_values().index:
        try:
            fits[mth] = fit_predict(mth, y, h)
        except Exception:
            continue
        if ttm > 0 and BAND[0] <= fits[mth][0].sum() / ttm <= BAND[1]:
            best = mth
            break
    m, lo, hi = fits.get(best) or fit_predict(best, y, h)
    idx = pd.period_range(y.index[-1] + 1, periods=h, freq="M")
    fc = pd.DataFrame({"target": name, "month": idx.to_timestamp(), "forecast": m, "lower80": lo, "upper80": hi, "model": best})
    ev.insert(0, "target", name)
    pr.insert(0, "target", name)
    return fc, ev, pr, best
