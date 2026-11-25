"""E8: robustness of the simpler long-only spot variant (the primary recommendation)."""
from common import *  # noqa
from e3_ensemble import build, stats_row

SY = ["BTCUSDT", "ETHUSDT"]
rows = []
for name, kw in [("long BASE", {}), ("cost stress 0.25%/side", {"spot_cost": 0.0025}), ("cost extreme 0.40%/side", {"spot_cost": 0.004}),
                 ("vt 0.3", {"vt": 0.3}), ("vt 0.8", {"vt": 0.8}), ("vt none", {"vt": None}),
                 ("lookback x0.5", {"scale": 0.5}), ("lookback x0.75", {"scale": 0.75}), ("lookback x1.5", {"scale": 1.5}), ("lookback x2", {"scale": 2.0}),
                 ("delay 1 day", {"lag": 6}), ("exec 1h", {"tf": "1h"}), ("exec 1d", {"tf": "1d"})]:
    r = build(SY, mode="long", vt=kw.pop("vt", 0.5), **kw)
    rows.append(stats_row(r, name))
t = pd.DataFrame(rows)
t.to_csv(RES / "e8_longonly_robust.csv", index=False)
print(t[["name", "dev_cagr_%", "dev_sharpe", "val_cagr_%", "val_sharpe", "hold_cagr_%", "hold_sharpe", "full_cagr_%", "full_maxdd_%", "full_sharpe"]].round(2).to_string())
