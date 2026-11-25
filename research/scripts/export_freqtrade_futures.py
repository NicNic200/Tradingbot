"""Export perp klines + funding to Freqtrade futures data format (mark price approximated by perp price)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from lib.data import load_klines, load_funding, resample

OUT = Path(__file__).resolve().parents[2] / "freqtrade" / "user_data" / "data" / "binance" / "futures"
OUT.mkdir(parents=True, exist_ok=True)
for s in sys.argv[1].split(","):
    pair = s.replace("USDT", "_USDT_USDT")
    h1 = load_klines(s, "1h", "futures")[["open", "high", "low", "close", "volume"]]
    for tf in ["1h", "4h"]:
        d = h1 if tf == "1h" else resample(load_klines(s, "1h", "futures"), "4h")[["open", "high", "low", "close", "volume"]]
        d.reset_index().to_feather(OUT / f"{pair}-{tf}-futures.feather")
    h1.reset_index().to_feather(OUT / f"{pair}-1h-mark.feather")
    f = load_funding(s)
    f.index = f.index.floor("h")
    f = f.groupby(level=0).sum()
    fr = pd.DataFrame({"open": f, "high": f, "low": f, "close": f, "volume": 0.0})
    fr.index.name = "date"
    fr.reset_index().to_feather(OUT / f"{pair}-1h-funding_rate.feather")
    print(pair, len(h1), len(fr))
