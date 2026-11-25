"""Load Binance archive zips into clean pandas DataFrames (UTC index, OHLCV) and cache as parquet."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "parquet"
CACHE.mkdir(parents=True, exist_ok=True)

KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
         "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def _read_kline_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name)
    first = raw[:200].decode(errors="ignore")
    header = 0 if first.startswith("open_time") else None
    df = pd.read_csv(io.BytesIO(raw), header=header, names=None if header == 0 else KCOLS)
    df.columns = KCOLS[: len(df.columns)]
    return df


def _to_ts(x: pd.Series) -> pd.DatetimeIndex:
    x = x.astype("int64")
    # Binance spot switched to microseconds on 2025-01-01
    us = x > 10**14
    ms = np.where(us, x // 1000, x)
    return pd.to_datetime(ms, unit="ms", utc=True)


def load_klines(symbol: str, tf: str = "1h", market: str = "spot", refresh: bool = False) -> pd.DataFrame:
    """Return OHLCV (+quote_volume, trades) indexed by candle open time (UTC)."""
    cache = CACHE / f"{market}_{symbol}_{tf}.parquet"
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)
    if tf == "4h" or tf == "1d":
        base = load_klines(symbol, "1h", market)
        return resample(base, tf)
    sub = "spot" if market == "spot" else "futures/um"
    files = sorted((RAW / sub / "monthly" / "klines" / symbol / tf).glob("*.zip"))
    files += sorted((RAW / sub / "daily" / "klines" / symbol / tf).glob("*.zip"))
    if not files:
        raise FileNotFoundError(f"no data for {market} {symbol} {tf}")
    parts = [_read_kline_zip(f) for f in files]
    df = pd.concat(parts, ignore_index=True)
    df.index = _to_ts(df["open_time"])
    df = df[["open", "high", "low", "close", "volume", "quote_volume", "trades"]].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "date"
    df.to_parquet(cache)
    return df


def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    rule = {"4h": "4h", "1d": "1D", "15m": "15min", "1h": "1h"}[tf]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
           "quote_volume": "sum", "trades": "sum"}
    out = df.resample(rule, origin="epoch", label="left", closed="left").agg(agg)
    # count of sub-candles per bucket: drop incomplete buckets (e.g. the still-forming last one)
    n = df["close"].resample(rule, origin="epoch", label="left", closed="left").count()
    expected = TF_MIN[tf] // TF_MIN.get(_infer_tf(df), 60)
    out = out[n >= expected].dropna()
    return out


def _infer_tf(df: pd.DataFrame) -> str:
    d = df.index.to_series().diff().median()
    m = int(d / pd.Timedelta(minutes=1))
    return {5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}[m]


def load_funding(symbol: str) -> pd.Series:
    """Funding rate per 8h settlement (fraction), indexed by settlement time (UTC)."""
    cache = CACHE / f"funding_{symbol}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)["rate"]
    files = sorted((RAW / "futures/um/monthly/fundingRate" / symbol).glob("*.zip"))
    parts = []
    for f in files:
        with zipfile.ZipFile(f) as zf:
            raw = zf.read(zf.namelist()[0])
        d = pd.read_csv(io.BytesIO(raw))
        d.columns = [c.strip() for c in d.columns]
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    s = pd.Series(d["last_funding_rate"].astype(float).values, index=_to_ts(d["calc_time"]), name="rate")
    s = s[~s.index.duplicated()].sort_index()
    s.to_frame().to_parquet(cache)
    return s


def quality_report(df: pd.DataFrame, tf: str) -> dict:
    step = pd.Timedelta(minutes=TF_MIN[tf])
    idx = df.index
    full = pd.date_range(idx[0], idx[-1], freq=step)
    missing = full.difference(idx)
    gaps = idx.to_series().diff()
    bad_ohlc = ((df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))).sum()
    ret = np.log(df["close"]).diff().abs()
    return {
        "start": str(idx[0]), "end": str(idx[-1]), "candles": len(df),
        "missing_candles": len(missing), "missing_pct": round(100 * len(missing) / len(full), 3),
        "largest_gap_h": round(gaps.max() / pd.Timedelta(hours=1), 1),
        "zero_volume": int((df["volume"] == 0).sum()), "bad_ohlc": int(bad_ohlc),
        "max_abs_logret": round(float(ret.max()), 4),
    }
