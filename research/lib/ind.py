"""Small indicator helpers (all causal: value at t uses data up to and including bar t)."""
import numpy as np
import pandas as pd
import talib


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return pd.Series(talib.EMA(s.to_numpy(float), timeperiod=n), s.index)


def rsi(s, n=14):
    return pd.Series(talib.RSI(s.to_numpy(float), timeperiod=n), s.index)


def atr(df, n=14):
    return pd.Series(talib.ATR(df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float), timeperiod=n), df.index)


def adx(df, n=14):
    return pd.Series(talib.ADX(df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float), timeperiod=n), df.index)


def donchian_hi(df, n):
    """Highest high of the previous n bars (excluding current bar)."""
    return df["high"].rolling(n, min_periods=n).max().shift(1)


def donchian_lo(df, n):
    return df["low"].rolling(n, min_periods=n).min().shift(1)


def realized_vol(close, n, periods_per_year):
    r = np.log(close).diff()
    return r.rolling(n, min_periods=n).std() * np.sqrt(periods_per_year)


def htf_to_ltf(htf: pd.Series, htf_minutes: int, ltf_index: pd.DatetimeIndex, ltf_minutes: int) -> pd.Series:
    """Map a higher-timeframe series (indexed by candle open) onto lower-timeframe bars without lookahead.

    The HTF candle opened at T is complete at T+htf. Its value becomes usable on the LTF bar whose
    CLOSE is T+htf, i.e. the LTF bar opened at T+htf-ltf (same convention as Freqtrade merge_informative_pair).
    """
    s = htf.copy()
    s.index = s.index + pd.Timedelta(minutes=htf_minutes - ltf_minutes)
    return s.reindex(ltf_index, method="ffill")


def state_from_signals(enter: pd.Series, exit_: pd.Series) -> pd.Series:
    """Convert entry/exit booleans to a 0/1 holding state (exit has priority)."""
    st = np.zeros(len(enter))
    e = enter.to_numpy(bool)
    x = exit_.to_numpy(bool)
    cur = 0
    for i in range(len(e)):
        if cur == 0 and e[i] and not x[i]:
            cur = 1
        elif cur == 1 and x[i]:
            cur = 0
        st[i] = cur
    return pd.Series(st, enter.index)
