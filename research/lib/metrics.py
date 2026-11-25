"""Performance metrics (crypto trades 365 days/year)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

PERIODS = {
    "dev": ("2018-01-01", "2022-12-31 23:59"),
    "val": ("2023-01-01", "2024-12-31 23:59"),
    "hold": ("2025-01-01", "2026-11-24 23:59"),
    "full": ("2018-01-01", "2026-11-24 23:59"),
}


def daily(eq: pd.Series) -> pd.Series:
    return eq.resample("1D").last().dropna()


def summarize(eq: pd.Series, trades: pd.DataFrame | None = None, exposure: pd.Series | None = None) -> dict:
    eq = eq.dropna()
    if len(eq) < 3:
        return {}
    d = daily(eq)
    r = d.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400), 1e-9)
    tot = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0
    peak = eq.cummax()
    dd = eq / peak - 1
    mdd = dd.min()
    # drawdown duration (days)
    under = dd < 0
    dur, best_dur, start = 0, 0, None
    for t, u in under.items():
        if u and start is None:
            start = t
        if not u and start is not None:
            best_dur = max(best_dur, (t - start).days)
            start = None
    if start is not None:
        best_dur = max(best_dur, (eq.index[-1] - start).days)
    sd = r.std()
    sharpe = r.mean() / sd * math.sqrt(365) if sd > 0 else 0.0
    dn = r[r < 0].std()
    sortino = r.mean() / dn * math.sqrt(365) if dn and dn > 0 else 0.0
    out = {
        "total_%": 100 * tot, "cagr_%": 100 * cagr, "maxdd_%": 100 * mdd, "dd_days": best_dur,
        "sharpe": sharpe, "sortino": sortino, "calmar": (cagr / abs(mdd)) if mdd < 0 else np.nan,
        "vol_%": 100 * sd * math.sqrt(365),
    }
    if exposure is not None:
        out["exposure_%"] = 100 * float(exposure.loc[eq.index[0]:eq.index[-1]].abs().mean())
    if trades is not None:
        t = trades
        out["trades"] = len(t)
        out["trades_per_y"] = len(t) / years
        if len(t):
            w = t["ret"] > 0
            gp, gl = t.loc[w, "ret"].sum(), -t.loc[~w, "ret"].sum()
            out["win_%"] = 100 * w.mean()
            out["pf"] = gp / gl if gl > 0 else np.inf
            out["avg_trade_%"] = 100 * t["ret"].mean()
            out["avg_bars"] = t["bars"].mean() if "bars" in t else np.nan
    return out


def slice_eq(eq: pd.Series, start, end) -> pd.Series:
    s = eq.loc[start:end]
    return s / s.iloc[0] if len(s) else s


def by_period(res: dict, periods=("dev", "val", "hold", "full")) -> pd.DataFrame:
    rows = {}
    for p in periods:
        a, b = PERIODS[p]
        eq = slice_eq(res["equity"], a, b)
        tr = res.get("trades")
        if tr is not None and len(tr):
            tr = tr[(tr["entry_time"] >= pd.Timestamp(a, tz="UTC")) & (tr["entry_time"] <= pd.Timestamp(b, tz="UTC"))]
        rows[p] = summarize(eq, tr, res.get("exposure"))
    return pd.DataFrame(rows).T


def by_year(eq: pd.Series) -> pd.Series:
    d = daily(eq)
    y = d.groupby(d.index.year).last()
    first = d.iloc[0]
    prev = pd.concat([pd.Series([first], index=[y.index[0] - 1]), y.iloc[:-1]])
    return pd.Series(100 * (y.values / prev.values - 1), index=y.index)


# ---------- overfitting statistics ----------

def probabilistic_sharpe(r: pd.Series, sr_benchmark: float = 0.0) -> float:
    """PSR (Bailey & Lopez de Prado), r = daily returns, SR in per-period units."""
    r = r.dropna()
    n = len(r)
    if n < 30 or r.std() == 0:
        return np.nan
    sr = r.mean() / r.std()
    sk = stats.skew(r)
    ku = stats.kurtosis(r, fisher=False)
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return float(stats.norm.cdf(z))


def deflated_sharpe(r: pd.Series, n_trials: int, sr_trials_std: float) -> float:
    """DSR: PSR against the expected max Sharpe of n_trials unskilled strategies (per-period SR units)."""
    emc = 0.5772156649
    if n_trials < 2:
        return probabilistic_sharpe(r, 0.0)
    sr0 = sr_trials_std * ((1 - emc) * stats.norm.ppf(1 - 1 / n_trials) + emc * stats.norm.ppf(1 - 1 / (n_trials * math.e)))
    return probabilistic_sharpe(r, sr0)


def block_bootstrap_cagr(r: pd.Series, block: int = 30, n: int = 2000, seed: int = 7) -> tuple[float, float, float]:
    """Stationary-ish block bootstrap of daily returns -> 5/50/95 percentile CAGR (%)."""
    rng = np.random.default_rng(seed)
    x = r.dropna().to_numpy()
    T = len(x)
    out = np.empty(n)
    for k in range(n):
        idx = []
        while len(idx) < T:
            s = rng.integers(0, T - block)
            idx.extend(range(s, s + block))
        path = x[np.array(idx[:T])]
        g = np.prod(1 + path) ** (365 / T) - 1
        out[k] = g
    return tuple(100 * np.percentile(out, [5, 50, 95]))
