"""E7: Walk-forward test of the *selection procedure* + corrected Deflated Sharpe Ratio.

Every 6 months, choose among 27 ensemble configurations (mode x vol-target x lookback-scale) the one with the
best trailing-3-year Sharpe, then trade it for the next 6 months.  The stitched out-of-sample curve shows
whether 'pick the best recent config' adds or destroys value compared with the fixed a-priori BASE config.
(Approximation: switching between configs at a boundary is assumed cost-free.)
"""
import math
from itertools import product

from common import *  # noqa
from e3_ensemble import build
from lib.metrics import deflated_sharpe, probabilistic_sharpe, summarize, daily

SY = ["BTCUSDT", "ETHUSDT"]
cfgs = list(product(["long", "ls_gated", "ls"], [0.3, 0.5, 0.8], [0.5, 1.0, 2.0]))
rets = {}
for mode, vt, sc in cfgs:
    eq = build(SY, mode=mode, vt=vt, scale=sc)["equity"]
    rets[(mode, vt, sc)] = daily(eq).pct_change().fillna(0)
R = pd.DataFrame(rets)
starts = pd.date_range("2021-01-01", "2026-07-01", freq="6MS", tz="UTC")
oos, picks = [], []
for a in starts:
    b = a + pd.DateOffset(months=6)
    train = R.loc[a - pd.DateOffset(years=3):a - pd.Timedelta(days=1)]
    sh = train.mean() / train.std() * math.sqrt(365)
    best = sh.idxmax()
    picks.append({"from": a.date(), "pick": best, "train_sharpe": round(sh.max(), 2)})
    oos.append(R.loc[a:b - pd.Timedelta(days=1), best])
oos = pd.concat(oos)
base = R[("ls_gated", 0.5, 1.0)].loc[oos.index]
avg = R.mean(axis=1).loc[oos.index]  # equal-weight blend of all 27 configs (no selection at all)
res = {}
for nm, r in [("walk_forward_selected", oos), ("fixed_BASE", base), ("blend_all_27", avg)]:
    eq = (1 + r).cumprod()
    s = summarize(eq)
    res[nm] = {k: s[k] for k in ["cagr_%", "maxdd_%", "sharpe", "sortino", "calmar"]}
print(pd.DataFrame(picks).to_string())
out = pd.DataFrame(res).T
print(out.round(2))
out.to_csv(RES / "e7_walkforward.csv")
pd.DataFrame(picks).to_csv(RES / "e7_wf_picks.csv", index=False)

# ---- corrected DSR: noise dispersion estimated from the trend-family trials only (E1, E2, E3, E6)
r = R[("ls_gated", 0.5, 1.0)].loc["2018-01-01":]
r = r[r.index >= r.ne(0).idxmax()]
tr = []
for f in ["e1_trials.csv", "e2_trials.csv", "e3_ensemble.csv", "e6_robust_variants.csv"]:
    t = pd.read_csv(RES / f)
    tr += list(t["full_sharpe"].dropna())
sd = np.std(np.array(tr)) / math.sqrt(365)
rows = []
for n in [len(tr), 232, 1000]:
    rows.append({"n_trials": n, "sr_std_ann": sd * math.sqrt(365), "DSR": deflated_sharpe(r, n, sd)})
rows.append({"n_trials": 1, "sr_std_ann": 0, "DSR": probabilistic_sharpe(r, 0.0)})
d = pd.DataFrame(rows)
print(d.round(4))
d.to_csv(RES / "e7_dsr.csv", index=False)
