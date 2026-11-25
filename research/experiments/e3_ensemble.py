"""E3: Trend ensemble (no single-parameter selection).

Signal set fixed a priori from standard lookbacks (days): SMA 20/50/100/200, Donchian 20/10 and 55/20,
time-series momentum 30/90/180, EMA crosses 10/30 and 20/100  -> 11 binary trend votes.
score = mean(vote) in [-1, 1].  score>0: long via SPOT.  score<0: short via PERP, optionally only in the
bear regime (close < SMA200d).  Position scaled by volatility targeting (30d realized vol).
"""
from common import *  # noqa
from lib.data import load_funding, resample
from lib.ind import sma, ema, donchian_hi, donchian_lo, realized_vol

TF = "4h"
B = BARS_PER_DAY[TF]
SPOT_COST, PERP_COST = 0.0015, 0.0010
ALL16 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT",
         "LINKUSDT", "AVAXUSDT", "DOTUSDT", "TRXUSDT", "ATOMUSDT", "XLMUSDT", "ETCUSDT", "BCHUSDT"]
PERP10 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT"]


def votes(df, B=B, scale=1.0):
    c = df["close"]
    L = lambda d: max(2, int(round(d * scale * B)))
    v = {}
    for n in [20, 50, 100, 200]:
        v[f"sma{n}"] = np.sign(c - sma(c, L(n)))
    for ne, nx in [(20, 10), (55, 20)]:
        hi_e, lo_e = donchian_hi(df, L(ne)), donchian_lo(df, L(ne))
        hi_x, lo_x = donchian_hi(df, L(nx)), donchian_lo(df, L(nx))
        st = np.zeros(len(c)); cur = 0
        U, D = (c > hi_e).to_numpy(), (c < lo_e).to_numpy()
        XL, XS = (c < lo_x).to_numpy(), (c > hi_x).to_numpy()
        for i in range(len(c)):
            if cur == 1 and XL[i]: cur = 0
            if cur == -1 and XS[i]: cur = 0
            if cur == 0 and U[i]: cur = 1
            elif cur == 0 and D[i]: cur = -1
            st[i] = cur
        v[f"donch{ne}"] = pd.Series(st, c.index)
    for lb in [30, 90, 180]:
        v[f"mom{lb}"] = np.sign(c / c.shift(L(lb)) - 1)
    for f, s in [(10, 30), (20, 100)]:
        v[f"ema{f}_{s}"] = np.sign(ema(c, L(f)) - ema(c, L(s)))
    V = pd.DataFrame(v)
    ready = V.notna().all(axis=1) & sma(c, 200 * B).notna()
    V = V.where(ready, 0.0)
    return V.fillna(0), ready


def score_and_size(df, vt=0.5, votes_df=None, B=B, scale=1.0):
    V, ready = votes_df if votes_df is not None else votes(df, B, scale)
    score = V.mean(axis=1).where(ready, 0.0)
    size = pd.Series(1.0, df.index)
    if vt:
        size = np.clip(vt / realized_vol(df["close"], 30 * B, 365 * B), 0, 1.0).fillna(0)
    bear = df["close"] < sma(df["close"], 200 * B)
    return score, size, bear


def build(symbols, mode="ls_gated", vt=0.5, band=0.05, spot_cost=SPOT_COST, perp_cost=PERP_COST, long_thr=0.0,
          start=None, tf=TF, scale=1.0, lag=0):
    B = BARS_PER_DAY[tf]
    """Returns run_weights result for an equal-weight (over available coins) portfolio."""
    spot = {s: load_klines(s, tf) for s in symbols}
    perp, fund = {}, {}
    for s in symbols:
        if mode != "long" and s in PERP10:
            p = load_klines(s, "1h", "futures")
            p = resample(p, tf) if tf != "1h" else p
            f = load_funding(s); f.index = f.index.floor("h"); f = f.groupby(level=0).sum()
            perp[s] = p; fund[s] = f
    idx = spot[symbols[0]].index
    for s in symbols[1:]:
        idx = idx.union(spot[s].index)
    Wl, Ws, avail = {}, {}, {}
    for s in symbols:
        df = spot[s]
        score, size, bear = score_and_size(df, vt, B=B, scale=scale)
        if lag:
            score, size, bear = score.shift(lag).fillna(0), size.shift(lag).fillna(0), bear.shift(lag).fillna(False)
        avail[s] = sma(df["close"], 200 * B).notna().reindex(idx).fillna(False)
        wl = (score.clip(lower=0) * size).where(score > long_thr, 0.0)
        if mode == "short_gated":
            wl = wl * 0.0
        Wl[s] = wl.reindex(idx).fillna(0)
        if mode != "long" and s in perp:
            ws = (score.clip(upper=0) * size)
            if mode in ("ls_gated", "short_gated"):
                ws = ws.where(bear, 0.0)
            # perps only tradable once perp data exists
            ws = ws.where(ws.index >= perp[s].index[0] + pd.Timedelta(days=1), 0.0)
            Ws[s] = ws.reindex(idx).fillna(0)
    navail = pd.DataFrame(avail).sum(axis=1).clip(lower=1)
    cols, O, W, F, C = [], {}, {}, {}, {}
    for s in symbols:
        O[s + "_spot"] = spot[s]["open"].reindex(idx)
        W[s + "_spot"] = Wl[s] / navail
        C[s + "_spot"] = spot_cost
        if s in Ws:
            O[s + "_perp"] = perp[s]["open"].reindex(idx)
            W[s + "_perp"] = Ws[s] / navail
            F[s + "_perp"] = fund[s].reindex(idx).fillna(0)
            C[s + "_perp"] = perp_cost
    O = pd.DataFrame(O).ffill()
    W = pd.DataFrame(W).fillna(0)
    W = W.where(O.notna(), 0.0)
    O = O.fillna(1.0)
    F = pd.DataFrame(F, index=idx).reindex(columns=O.columns).fillna(0) if F else None
    if start is not None:
        keep = O.index >= pd.Timestamp(start, tz="UTC")
        O, W = O[keep], W[keep]
        F = F[keep] if F is not None else None
    res = run_weights(O, W, cost=C, funding=F, band=band)
    res["weights"] = W
    return res


def stats_row(res, name):
    out = {"name": name}
    for p in ["dev", "val", "hold", "full"]:
        a, b = PERIODS[p]
        s = summarize(slice_eq(res["equity"], a, b), None, res["exposure"])
        for m in ["cagr_%", "maxdd_%", "sharpe", "exposure_%"]:
            out[f"{p}_{m}"] = s.get(m)
    t = res["turnover"].loc[PERIODS["full"][0]:]
    out["turnover_per_y"] = t.sum() / ((t.index[-1] - t.index[0]).days / 365)
    return out


if __name__ == "__main__":
    rows = []
    for mode in ["long", "ls_gated", "ls"]:
        for vt in [None, 0.5]:
            r = build(["BTCUSDT", "ETHUSDT"], mode=mode, vt=vt)
            rows.append(stats_row(r, f"BTC+ETH {mode} vt={vt}"))
            print(rows[-1]["name"], flush=True)
    for mode in ["long", "ls_gated"]:
        r = build(ALL16, mode=mode, vt=0.5)
        rows.append(stats_row(r, f"16coins {mode} vt=0.5"))
        print(rows[-1]["name"], flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e3_ensemble.csv", index=False)
    print(t.round(2).to_string())
