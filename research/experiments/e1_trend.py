"""E1: long-only trend-following families on BTC+ETH spot (4h execution bars).

Selection is done on the DEV period only (2018-2022).  All trials are written to results/e1_trials.csv.
"""
from itertools import product

from common import *  # noqa
from lib.ind import sma, ema, atr, donchian_hi, donchian_lo, realized_vol, state_from_signals

SYMS = ["BTCUSDT", "ETHUSDT"]
TF = "4h"
B = BARS_PER_DAY[TF]
DATA = {s: load_klines(s, TF) for s in SYMS}
DAILY = {s: load_klines(s, "1d") for s in SYMS}


def vt_size(df, target):
    if target is None:
        return 1.0
    vol = realized_vol(df["close"], 30 * B, 365 * B)
    return np.clip(target / vol, 0, 1.0).fillna(0).to_numpy()


def strat(df, fam, p):
    c = df["close"]
    trail = None
    if fam == "sma":
        m = sma(c, p["n"] * B)
        st = (c > m).astype(int)
        ent, ext = st.diff() == 1, st.diff() == -1
    elif fam == "ema_x":
        f, s = ema(c, p["f"] * B), ema(c, p["s"] * B)
        st = (f > s).astype(int)
        ent, ext = st.diff() == 1, st.diff() == -1
    elif fam == "donch":
        ent = c > donchian_hi(df, p["ne"] * B)
        ext = c < donchian_lo(df, p["nx"] * B)
    elif fam == "donch_atr":
        ent = c > donchian_hi(df, p["ne"] * B)
        ext = pd.Series(False, df.index)
        trail = (p["k"] * atr(df, 14 * B) / c).to_numpy()  # chandelier distance as fraction of price
    elif fam == "tsmom":
        # daily decision: sign of L-day return, evaluated only on the 4h bar closing at 00:00 UTC
        mom = c / c.shift(p["L"] * B) - 1
        is_day_close = (df.index + pd.Timedelta(hours=4)).hour == 0
        st = pd.Series(np.nan, df.index)
        st[is_day_close] = (mom[is_day_close] > 0).astype(float)
        st = st.ffill().fillna(0)
        ent, ext = st.diff() == 1, st.diff() == -1
    else:
        raise ValueError(fam)
    return ent.fillna(False).to_numpy(), ext.fillna(False).to_numpy(), trail


GRID = {
    "sma": [{"n": n} for n in [20, 50, 100, 150, 200]],
    "ema_x": [{"f": f, "s": s} for f, s in [(10, 30), (10, 50), (20, 50), (20, 100), (50, 200)]],
    "donch": [{"ne": ne, "nx": nx} for ne, nx in product([20, 30, 55, 100], [10, 20, 30]) if nx < ne],
    "donch_atr": [{"ne": ne, "k": k} for ne, k in product([20, 30, 55], [3, 4, 5])],
    "tsmom": [{"L": L} for L in [30, 60, 90, 120, 180]],
}
VT = [None, 0.5]


def run_cfg(fam, p, vt, cost=COST, syms=SYMS, data=None):
    data = data or DATA
    res = []
    for s in syms:
        df = data[s]
        ent, ext, trail = strat(df, fam, p)
        res.append(run_trades(df, ent, ext, trail=trail, size=vt_size(df, vt), cost=cost))
    return combine(res)


if __name__ == "__main__":
    rows = []
    for fam, plist in GRID.items():
        for p, vt in product(plist, VT):
            r = run_cfg(fam, p, vt)
            rows.append({"family": fam, "params": str(p), "vt": vt or 0, **period_row(r)})
            print(fam, p, vt, f"dev Sharpe {rows[-1]['dev_sharpe']:.2f}", flush=True)
    bh = combine([buy_hold(DATA[s]) for s in SYMS])
    rows.append({"family": "buy_hold_5050", "params": "", "vt": 0, **period_row(bh)})
    for s in SYMS:
        rows.append({"family": f"buy_hold_{s}", "params": "", "vt": 0, **period_row(buy_hold(DATA[s]))})
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e1_trials.csv", index=False)
    cols = ["family", "params", "vt", "dev_cagr_%", "dev_maxdd_%", "dev_sharpe", "dev_trades", "dev_exposure_%"]
    print(t.sort_values("dev_sharpe", ascending=False)[cols].round(2).to_string())
