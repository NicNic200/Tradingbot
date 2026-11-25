import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

from lib.data import load_klines
from lib.engine import run_trades, run_weights
from lib.metrics import PERIODS, by_period, summarize, slice_eq, by_year, daily

RES = ROOT / "results"
COST = 0.0015       # 0.10 % fee + 0.05 % slippage per side
COST_STRESS = 0.0025  # 0.10 % fee + 0.15 % slippage per side
BARS_PER_DAY = {"1h": 24, "4h": 6, "1d": 1, "15m": 96, "5m": 288}

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)


def combine(results: list[dict], weights=None) -> dict:
    """Sum of independent sleeves (no rebalancing): each sleeve starts with an equal share of capital."""
    n = len(results)
    weights = weights or [1 / n] * n
    idx = results[0]["equity"].index
    for r in results[1:]:
        idx = idx.union(r["equity"].index)
    eq = sum(w * r["equity"].reindex(idx).ffill().bfill() for w, r in zip(weights, results))
    expo = sum(w * r["exposure"].reindex(idx).fillna(0) for w, r in zip(weights, results))
    trades = pd.concat([r["trades"] for r in results if len(r["trades"])], ignore_index=True) if any(len(r["trades"]) for r in results) else pd.DataFrame()
    return {"equity": eq, "exposure": expo, "trades": trades}


def buy_hold(df: pd.DataFrame, cost=COST) -> dict:
    ent = np.zeros(len(df), bool)
    ent[0] = True
    return run_trades(df, ent, None, cost=cost)


def period_row(res: dict, prefix="") -> dict:
    t = by_period(res)
    out = {}
    for p in ["dev", "val", "hold", "full"]:
        if p in t.index:
            for k in ["cagr_%", "maxdd_%", "sharpe", "trades", "exposure_%", "pf", "win_%"]:
                if k in t.columns:
                    out[f"{p}_{k}"] = t.loc[p, k]
    return out
