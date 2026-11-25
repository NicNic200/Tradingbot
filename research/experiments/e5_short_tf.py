"""E5: shorter timeframes on BTC+ETH spot (long-only): mean reversion (1h/15m) and breakouts (15m/5m).

Question: is there anything left after realistic costs?  Each config is run with base costs
(0.15 %/side) and with an optimistic low-cost scenario (0.05 %/side, e.g. maker fills w/o slippage).
"""
from itertools import product

from common import *  # noqa
from lib.ind import sma, ema, rsi, atr, donchian_hi
from lib.metrics import summarize

SYMS = ["BTCUSDT", "ETHUSDT"]


def mr_signals(df, tf, p):
    b = BARS_PER_DAY[tf]
    c = df["close"]
    r2 = rsi(c, 2)
    trend = c > sma(c, 50 * b) if p["trend"] else pd.Series(True, df.index)
    ent = (r2 < p["thr"]) & trend
    ext = (c > sma(c, 5)) | (r2 > 70)
    return ent.fillna(False).to_numpy(), ext.fillna(False).to_numpy()


def bo_signals(df, tf, p):
    b = BARS_PER_DAY[tf]
    c = df["close"]
    trend = ema(c, 50 * b // 6) > ema(c, 200 * b // 6)  # 4h-EMA50/200 equivalent on this timeframe
    vol_ok = df["volume"] > df["volume"].rolling(p["n"]).mean() * 1.5
    ent = (c > donchian_hi(df, p["n"])) & trend & vol_ok
    a = atr(df, 14) / c
    return ent.fillna(False).to_numpy(), (p["sl"] * a).to_numpy(), (p["tp"] * a).to_numpy()


def run_set(tf, kind, p, cost):
    res = []
    for s in SYMS:
        df = load_klines(s, tf).loc["2019-01-01":]
        if kind == "mr":
            ent, ext = mr_signals(df, tf, p)
            res.append(run_trades(df, ent, ext, stop=0.05, max_bars=p["tmax"] * BARS_PER_DAY[tf] // 24, cost=cost))
        else:
            ent, sl, tp = bo_signals(df, tf, p)
            res.append(run_trades(df, ent, None, stop=sl, tp=tp, max_bars=p["tmax"], cost=cost))
    return combine(res)


GRID = {
    ("mr", "1h"): [{"thr": t, "trend": tr, "tmax": 48} for t, tr in product([5, 10, 20], [True, False])],
    ("mr", "15m"): [{"thr": t, "trend": tr, "tmax": 24} for t, tr in product([5, 10], [True, False])],
    ("bo", "15m"): [{"n": n, "sl": 2, "tp": tp, "tmax": 96} for n, tp in product([48, 96], [3, 6])],
    ("bo", "5m"): [{"n": n, "sl": 2, "tp": tp, "tmax": 288} for n, tp in product([48, 144], [3, 6])],
}

if __name__ == "__main__":
    rows = []
    for (kind, tf), plist in GRID.items():
        for p in plist:
            for cname, cost in [("base", COST), ("lowcost", 0.0005)]:
                r = run_set(tf, kind, p, cost)
                row = {"kind": kind, "tf": tf, "params": str(p), "cost": cname}
                for per in ["dev", "val", "hold"]:
                    a, b = PERIODS[per]
                    a = max(pd.Timestamp(a), pd.Timestamp("2019-02-01")).strftime("%Y-%m-%d")
                    tr = r["trades"]
                    tr = tr[(tr["entry_time"] >= pd.Timestamp(a, tz="UTC")) & (tr["entry_time"] <= pd.Timestamp(b, tz="UTC"))]
                    s = summarize(slice_eq(r["equity"], a, b), tr, r["exposure"])
                    for m in ["cagr_%", "maxdd_%", "sharpe", "trades_per_y", "avg_trade_%", "win_%"]:
                        row[f"{per}_{m}"] = s.get(m)
                rows.append(row)
                print(kind, tf, p, cname, round(row["dev_cagr_%"], 1), round(row["val_cagr_%"], 1), round(row["hold_cagr_%"], 1), flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(RES / "e5_short_tf.csv", index=False)
    print(t.round(2).to_string())
