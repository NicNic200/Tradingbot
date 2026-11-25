"""E9: Funding carry (delta-neutral: long spot + short perp of equal notional) on BTC+ETH.

Capital per coin is split 50/50: half buys spot, half is margin for a 1x short perp of the same notional.
-> notional per leg = 0.5 of the coin's capital share.  Return ~ 0.5 * funding received - costs +/- basis noise.
Rules (fixed a priori): 'always' = permanently on; 'filter' = on only while the trailing 3-day mean funding rate
is positive (decided daily at 00:00 UTC).  Costs: spot 0.15 %/side, perp 0.10 %/side.
Not modelled: exchange/counterparty risk, margin calls of the short leg in rallies (needs wallet transfers),
borrow/transfer frictions.  Research only.
"""
from common import *  # noqa
from lib.data import load_funding, resample
from lib.metrics import summarize, by_year

SY = ["BTCUSDT", "ETHUSDT"]
P = {"dev": ("2020-03-01", "2022-12-31 23:59"), "val": PERIODS["val"], "hold": PERIODS["hold"], "full": ("2020-03-01", "2026-10-31 23:59")}


def build(rule="filter", thr=0.0):
    O, W, F, C = {}, {}, {}, {}
    for s in SY:
        sp = load_klines(s, "1h", "spot")
        pp = load_klines(s, "1h", "futures")
        f = load_funding(s); f.index = f.index.floor("h"); f = f.groupby(level=0).sum()
        idx = pp.index.intersection(sp.index)
        idx = idx[idx <= f.index[-1]]
        fr = f.reindex(idx).fillna(0.0)
        if rule == "always":
            on = pd.Series(1.0, idx)
        else:
            m = f.rolling(9).mean().reindex(idx).ffill()
            daily_dec = pd.Series(np.where(idx.hour == 0, (m > thr).astype(float), np.nan), idx).ffill().fillna(0)
            on = daily_dec
        w = 0.5 * on / len(SY)
        O[s + "_spot"], W[s + "_spot"], C[s + "_spot"] = sp["open"].reindex(idx), w, 0.0015
        O[s + "_perp"], W[s + "_perp"], C[s + "_perp"] = pp["open"].reindex(idx), -w, 0.0010
        F[s + "_perp"] = fr
    O = pd.DataFrame(O).ffill().dropna()
    W = pd.DataFrame(W).reindex(O.index).fillna(0)
    F = pd.DataFrame(F).reindex(O.index).fillna(0).reindex(columns=O.columns).fillna(0)
    # band rebalancing is essential: an un-rebalanced hedge grows its notional with price (hidden leverage)
    return run_weights(O, W, cost=C, funding=F, band=0.02)


if __name__ == "__main__":
    rows = []
    for rule, thr in [("always", 0.0), ("filter", 0.0), ("filter", 0.0001)]:
        r = build(rule, thr)
        row = {"rule": rule, "thr_per_8h": thr}
        for k, (a, b) in P.items():
            s = summarize(slice_eq(r["equity"], a, b), None, r["exposure"])
            for m in ["cagr_%", "maxdd_%", "sharpe", "exposure_%"]:
                row[f"{k}_{m}"] = s.get(m)
        rows.append(row)
        print(rule, thr, by_year(r["equity"].loc["2020-03-01":]).round(1).to_dict(), flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e9_carry.csv", index=False)
    print(t.round(2).to_string())
