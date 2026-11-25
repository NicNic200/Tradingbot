"""E6: robustness of the trend-ensemble finalist (BTC+ETH, ls_gated, vt=0.5, 4h, band 0.05)."""
import math

from common import *  # noqa
from e3_ensemble import build, stats_row, ALL16, PERP10
from lib.metrics import deflated_sharpe, probabilistic_sharpe, block_bootstrap_cagr, by_year, daily

BASE = dict(symbols=["BTCUSDT", "ETHUSDT"], mode="ls_gated", vt=0.5)
out = {}


def variant(name, **kw):
    cfg = {**BASE, **kw}
    r = build(**cfg)
    row = stats_row(r, name)
    print(f"{name:38s} dev {row['dev_cagr_%']:6.1f}%/{row['dev_sharpe']:.2f}  val {row['val_cagr_%']:6.1f}%/{row['val_sharpe']:.2f}  "
          f"hold {row['hold_cagr_%']:6.1f}%/{row['hold_sharpe']:.2f}  full {row['full_cagr_%']:6.1f}% DD {row['full_maxdd_%']:.1f}%", flush=True)
    return r, row


rows = []
base_r, row = variant("BASE")
rows.append(row)
# 1) costs
for sc, pc, nm in [(0.0025, 0.0020, "cost stress (0.25/0.20 %/side)"), (0.0040, 0.0030, "cost extreme (0.40/0.30 %/side)")]:
    rows.append(variant(nm, spot_cost=sc, perp_cost=pc)[1])
# 2) vol target
for vt in [0.3, 0.4, 0.6, 0.8, None]:
    rows.append(variant(f"vt={vt}", vt=vt)[1])
# 3) lookback scale (parameter neighbourhood)
for sc in [0.5, 0.75, 1.25, 1.5, 2.0]:
    rows.append(variant(f"lookback x{sc}", scale=sc)[1])
# 4) execution timeframe / delay / rebalancing band
rows.append(variant("exec 1h bars", tf="1h")[1])
rows.append(variant("exec 1d bars", tf="1d")[1])
rows.append(variant("delay +1 bar (4h)", lag=1)[1])
rows.append(variant("delay +6 bars (1 day)", lag=6)[1])
for band in [0.02, 0.10, 0.20]:
    rows.append(variant(f"band {band}", band=band)[1])
# 5) modes
rows.append(variant("long-only spot", mode="long")[1])
rows.append(variant("long/short ungated", mode="ls")[1])
pd.DataFrame(rows).to_csv(RES / "e6_robust_variants.csv", index=False)

# 6) per-coin generalisation (same parameters, no retuning)
coin_rows = []
for s in ALL16:
    for mode in (["long", "ls_gated"] if s in PERP10 else ["long"]):
        r = build([s], mode=mode, vt=0.5)
        st = stats_row(r, f"{s} {mode}")
        bh = buy_hold(load_klines(s, "4h"))
        bst = {}
        for p in ["dev", "val", "hold", "full"]:
            a, b = PERIODS[p]
            from lib.metrics import summarize
            sm = summarize(slice_eq(bh["equity"], a, b))
            bst[f"bh_{p}_cagr_%"] = sm.get("cagr_%")
            bst[f"bh_{p}_maxdd_%"] = sm.get("maxdd_%")
        coin_rows.append({**st, **bst})
coins = pd.DataFrame(coin_rows)
coins.to_csv(RES / "e6_per_coin.csv", index=False)
print(coins[["name", "dev_cagr_%", "val_cagr_%", "hold_cagr_%", "full_cagr_%", "full_maxdd_%", "full_sharpe", "bh_full_cagr_%", "bh_full_maxdd_%"]].round(1).to_string())
for mode in ["long", "ls_gated"]:
    c = coins[coins.name.str.endswith(mode)]
    print(mode, "share positive dev/val/hold/full:", [round((c[f"{p}_cagr_%"] > 0).mean(), 2) for p in ["dev", "val", "hold", "full"]],
          "share DD better than B&H:", round((c["full_maxdd_%"] > c["bh_full_maxdd_%"]).mean(), 2))

# 7) yearly returns vs buy & hold
bh = combine([buy_hold(load_klines(s, "4h")) for s in ["BTCUSDT", "ETHUSDT"]])
yr = pd.DataFrame({"strategy_%": by_year(base_r["equity"].loc["2018-01-01":]), "buyhold_5050_%": by_year(bh["equity"].loc["2018-01-01":])})
yr.to_csv(RES / "e6_yearly.csv")
print(yr.round(1).to_string())

# 8) statistics: PSR, DSR (n_trials = all configurations evaluated in E1-E5), bootstrap
r = daily(base_r["equity"].loc["2018-01-01":]).pct_change().dropna()
trials = []
for f, col in [("e1_trials.csv", "full_sharpe"), ("e2_trials.csv", "full_sharpe"), ("e4_rotation.csv", "full_sharpe"), ("e3_ensemble.csv", "full_sharpe")]:
    t = pd.read_csv(RES / f)
    trials += list(t[col].dropna())
t5 = pd.read_csv(RES / "e5_short_tf.csv")
trials += list(t5["dev_sharpe"].dropna())
n_trials = len(trials) + len(rows)
sr_std = np.std(np.array(trials) / math.sqrt(365))
stats_out = {
    "n_trials": n_trials,
    "sharpe_ann": r.mean() / r.std() * math.sqrt(365),
    "PSR_vs_0": probabilistic_sharpe(r, 0.0),
    "DSR": deflated_sharpe(r, n_trials, sr_std),
}
for nm, (a, b) in [("hold", PERIODS["hold"]), ("full", PERIODS["full"])]:
    rr = daily(base_r["equity"].loc[a:b]).pct_change().dropna()
    lo, med, hi = block_bootstrap_cagr(rr, block=30, n=2000)
    stats_out[f"bootstrap_cagr_{nm}_5/50/95_%"] = (round(lo, 1), round(med, 1), round(hi, 1))
    stats_out[f"PSR_{nm}"] = probabilistic_sharpe(rr, 0.0)
print(stats_out)
pd.Series(stats_out).to_csv(RES / "e6_stats.csv")
base_r["equity"].to_frame("equity").to_parquet(RES / "final_equity.parquet")
