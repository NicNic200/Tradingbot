"""Export cached Binance klines to Freqtrade's feather format (user_data/data/binance)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.data import load_klines

OUT = Path(__file__).resolve().parents[2] / "freqtrade" / "user_data" / "data" / "binance"
OUT.mkdir(parents=True, exist_ok=True)
SYMS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["BTCUSDT", "ETHUSDT"]
TFS = sys.argv[2].split(",") if len(sys.argv) > 2 else ["1h", "4h", "1d"]
for s in SYMS:
    for tf in TFS:
        df = load_klines(s, tf, "spot")[["open", "high", "low", "close", "volume"]].reset_index()
        pair = s.replace("USDT", "_USDT")
        df.to_feather(OUT / f"{pair}-{tf}.feather")
        print(pair, tf, len(df), df["date"].iloc[0], df["date"].iloc[-1])
