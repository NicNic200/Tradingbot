"""E2: trend-following on USDT-M perpetuals (BTC+ETH): long-only vs long/short, incl. real funding.

Futures data start 2020 -> DEV = 2020-2022 for this family (VAL 2023-2024, HOLD 2025-2026 unchanged).
Costs per side: 0.05 % taker fee + 0.05 % slippage = 0.10 % (stress: 0.20 %).  Leverage 1x.
"""
from itertools import product

from common import *  # noqa
from lib.data import load_funding
from lib.ind import sma, ema, donchian_hi, donchian_lo, realized_vol
from lib.metrics import summarize

SYMS = ["BTCUSDT", "ETHUSDT"]
TF = "4h"
B = BARS_PER_DAY[TF]
FCOST, FCOST_STRESS = 0.0010, 0.0020
P2 = {"dev": ("2020-03-01", "2022-12-31 23:59"), "val": PERIODS["val"], "hold": PERIODS["hold"], "full": ("2020-03-01", "2026-11-24 23:59")}


def fut_data():
    px, fund = {}, {}
    for s in SYMS:
        df = load_klines(s, "1h", "futures")
        from lib.data import resample
        df4 = resample(df, "4h")
        f = load_funding(s)
        f.index = f.index.floor("h")
        f = f.groupby(level=0).sum()
        # funding settles at 00/08/16 UTC = open of a 4h bar
        px[s] = df4
        fund[s] = f.reindex(df4.index).fillna(0.0)
    return px, fund


def trend_state(df, fam, p):
    """+1 uptrend, -1 downtrend (symmetric rules)."""
    c = df["close"]
    if fam == "sma":
        m = sma(c, p["n"] * B)
        st = np.sign(c - m)
    elif fam == "ema_x":
        st = np.sign(ema(c, p["f"] * B) - ema(c, p["s"] * B))
    elif fam == "donch":
        up = c > donchian_hi(df, p["ne"] * B)
        dn = c < donchian_lo(df, p["ne"] * B)
        exl = c < donchian_lo(df, p["nx"] * B)
        exs = c > donchian_hi(df, p["nx"] * B)
        st = np.zeros(len(c)); cur = 0
        U, D, XL, XS = up.to_numpy(), dn.to_numpy(), exl.to_numpy(), exs.to_numpy()
        for i in range(len(c)):
            if cur == 1 and XL[i]: cur = 0
            if cur == -1 and XS[i]: cur = 0
            if cur == 0 and U[i]: cur = 1
            elif cur == 0 and D[i]: cur = -1
            st[i] = cur
        st = pd.Series(st, c.index)
    elif fam == "tsmom":
        mom = c / c.shift(p["L"] * B) - 1
        day_close = (df.index + pd.Timedelta(hours=4)).hour == 0
        st = pd.Series(np.nan, c.index)
        st[day_close] = np.sign(mom[day_close])
        st = st.ffill()
    return pd.Series(st, c.index).fillna(0)


def weights_from_state(df, st, mode, vt):
    if mode == "long":
        st = st.clip(lower=0)
    elif mode == "short_bear":
        # long in uptrend; short only when price is also below the 200-day SMA (bear regime)
        bear = df["close"] < sma(df["close"], 200 * B)
        st = st.where((st > 0) | bear, 0)
    size = pd.Series(1.0, df.index)
    if vt:
        vol = realized_vol(df["close"], 30 * B, 365 * B)
        size = np.clip(vt / vol, 0, 1.0)
    # size is fixed at the moment the state changes (no daily rebalancing churn)
    chg = st.diff().fillna(st) != 0
    sz = size.where(chg).ffill().fillna(0)
    return st * sz


GRID = {
    "sma": [{"n": n} for n in [20, 50, 100, 200]],
    "ema_x": [{"f": f, "s": s} for f, s in [(10, 30), (20, 50), (20, 100)]],
    "donch": [{"ne": ne, "nx": nx} for ne, nx in [(20, 10), (30, 10), (55, 20), (100, 30)]],
    "tsmom": [{"L": L} for L in [30, 60, 120]],
}


def run(px, fund, fam, p, mode, vt, cost=FCOST):
    W = pd.DataFrame({s: weights_from_state(px[s], trend_state(px[s], fam, p), mode, vt) / len(SYMS) for s in SYMS})
    O = pd.DataFrame({s: px[s]["open"] for s in SYMS}).dropna()
    F = pd.DataFrame(fund).reindex(O.index).fillna(0)
    return run_weights(O, W.reindex(O.index).fillna(0), cost=cost, funding=F)


def rowstats(res):
    out = {}
    for k, (a, b) in P2.items():
        s = summarize(slice_eq(res["equity"], a, b), None, res["exposure"])
        for m in ["cagr_%", "maxdd_%", "sharpe"]:
            out[f"{k}_{m}"] = s.get(m)
    return out


if __name__ == "__main__":
    px, fund = fut_data()
    rows = []
    for fam, plist in GRID.items():
        for p, mode, vt in product(plist, ["long", "longshort", "short_bear"], [None, 0.5]):
            r = run(px, fund, fam, p, mode, vt)
            rows.append({"family": fam, "params": str(p), "mode": mode, "vt": vt or 0, **rowstats(r)})
    # buy & hold perps 50/50 (incl. funding)
    O = pd.DataFrame({s: px[s]["open"] for s in SYMS}).dropna()
    W = pd.DataFrame(0.5, index=O.index, columns=SYMS)
    bh = run_weights(O, W, cost=FCOST, funding=pd.DataFrame(fund).reindex(O.index).fillna(0))
    rows.append({"family": "buy_hold_perp_5050", "params": "", "mode": "long", "vt": 0, **rowstats(bh)})
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e2_trials.csv", index=False)
    print(t.round(2).to_string())
    print(t.groupby(["mode", "vt"])[["dev_sharpe", "val_sharpe", "hold_sharpe", "full_sharpe", "hold_cagr_%"]].median().round(2))
    # average funding paid by a permanent long (annualized)
    for s in SYMS:
        f = fund[s]
        print(s, "funding long pays p.a. 2020-26: %.2f %%" % (100 * f.sum() / ((f.index[-1] - f.index[0]).days / 365)))
