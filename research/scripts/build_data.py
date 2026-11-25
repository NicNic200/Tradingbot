"""Build parquet cache from raw zips and write a data quality report."""
import sys, json
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import pandas as pd
from lib.data import load_klines, load_funding, quality_report
from scripts.make_urls import SPOT_1H, SPOT_FAST, FUT

rows = []
for s in SPOT_1H:
    df = load_klines(s, "1h", "spot", refresh=True)
    rows.append({"market": "spot", "symbol": s, "tf": "1h", **quality_report(df, "1h")})
for tf, syms in SPOT_FAST.items():
    for s in syms:
        df = load_klines(s, tf, "spot", refresh=True)
        rows.append({"market": "spot", "symbol": s, "tf": tf, **quality_report(df, tf)})
for s in FUT:
    df = load_klines(s, "1h", "futures", refresh=True)
    rows.append({"market": "futures", "symbol": s, "tf": "1h", **quality_report(df, "1h")})
    f = load_funding(s)
    rows.append({"market": "funding", "symbol": s, "tf": "8h", "start": str(f.index[0]), "end": str(f.index[-1]), "candles": len(f),
                 "mean_rate_pct": round(100 * f.mean(), 4), "max_abs_logret": round(float(f.abs().max()), 4)})
rep = pd.DataFrame(rows)
rep.to_csv("results/data_quality.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(rep.to_string())
