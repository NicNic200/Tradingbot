"""E4: weekly cross-sectional momentum rotation across 16 spot coins with BTC regime filter.

Universe chosen today -> survivorship bias (coins that were delisted/crashed to irrelevance are missing).
"""
from itertools import product

from common import *  # noqa
from lib.ind import sma
from lib.metrics import summarize
from e3_ensemble import ALL16


def build(L=60, k=3, regime=True, abs_filter=True, cost=COST):
    D = {s: load_klines(s, "1d") for s in ALL16}
    C = pd.DataFrame({s: D[s]["close"] for s in ALL16})
    O = pd.DataFrame({s: D[s]["open"] for s in ALL16})
    mom = C / C.shift(L) - 1
    eligible = C.notna() & C.shift(200).notna()
    mom = mom.where(eligible)
    btc_ok = C["BTCUSDT"] > sma(C["BTCUSDT"], 200)
    W = pd.DataFrame(0.0, index=C.index, columns=ALL16)
    rebal = C.index.dayofweek == 6  # decide on Sunday close, execute Monday open
    cur = pd.Series(0.0, index=ALL16)
    for t in C.index:
        if rebal[C.index.get_loc(t)]:
            cur = pd.Series(0.0, index=ALL16)
            if (not regime) or btc_ok.loc[t]:
                m = mom.loc[t].dropna()
                if abs_filter:
                    m = m[m > 0]
                top = m.sort_values(ascending=False).head(k).index
                if len(top):
                    cur[top] = 1.0 / k
        W.loc[t] = cur
    return run_weights(O.ffill().fillna(1.0), W.where(O.notna(), 0.0), cost=cost)


if __name__ == "__main__":
    rows = []
    for L, k, reg in product([30, 60, 90], [3, 5], [True, False]):
        r = build(L, k, reg)
        row = {"L": L, "k": k, "regime": reg}
        for per in ["dev", "val", "hold", "full"]:
            a, b = PERIODS[per]
            s = summarize(slice_eq(r["equity"], a, b), None, r["exposure"])
            for m in ["cagr_%", "maxdd_%", "sharpe", "exposure_%"]:
                row[f"{per}_{m}"] = s.get(m)
        rows.append(row)
        print(row["L"], row["k"], row["regime"], round(row["dev_sharpe"], 2), round(row["val_sharpe"], 2), round(row["hold_sharpe"], 2), flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e4_rotation.csv", index=False)
    print(t.round(2).to_string())
