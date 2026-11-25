"""Generate download URLs for the public Binance data archive (data.binance.vision)."""
import sys
from datetime import date, timedelta

BASE = "https://data.binance.vision/data"
SPOT_1H = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LTCUSDT",
           "LINKUSDT","AVAXUSDT","DOTUSDT","TRXUSDT","ATOMUSDT","XLMUSDT","ETCUSDT","BCHUSDT"]
SPOT_FAST = {"15m": ["BTCUSDT","ETHUSDT","SOLUSDT"], "5m": ["BTCUSDT","ETHUSDT"]}
FUT = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LTCUSDT","LINKUSDT","AVAXUSDT"]

def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1

END_MONTH = (2026, 10)


def main():
    DAYS = [date(2026, 11, 1) + timedelta(d) for d in range(24)]  # 2026-11-01 .. 2026-11-24
    out = []
    for s in SPOT_1H:
        for y, m in months((2017, 8), END_MONTH):
            out.append(f"{BASE}/spot/monthly/klines/{s}/1h/{s}-1h-{y}-{m:02d}.zip")
        for d in DAYS:
            out.append(f"{BASE}/spot/daily/klines/{s}/1h/{s}-1h-{d.isoformat()}.zip")
    for tf, syms in SPOT_FAST.items():
        for s in syms:
            for y, m in months((2019, 1), END_MONTH):
                out.append(f"{BASE}/spot/monthly/klines/{s}/{tf}/{s}-{tf}-{y}-{m:02d}.zip")
            for d in DAYS:
                out.append(f"{BASE}/spot/daily/klines/{s}/{tf}/{s}-{tf}-{d.isoformat()}.zip")
    for s in FUT:
        for y, m in months((2019, 9), END_MONTH):
            out.append(f"{BASE}/futures/um/monthly/klines/{s}/1h/{s}-1h-{y}-{m:02d}.zip")
            out.append(f"{BASE}/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{y}-{m:02d}.zip")
        for d in DAYS:
            out.append(f"{BASE}/futures/um/daily/klines/{s}/1h/{s}-1h-{d.isoformat()}.zip")
    print("\n".join(out))


if __name__ == "__main__":
    main()
