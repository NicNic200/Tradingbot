"""Trend-following pullback strategy for Freqtrade spot dry-run/backtesting.

Research candidate, not an established profitable trading strategy.
"""
from pandas import DataFrame
import talib.abstract as ta
from technical import qtpylib
from freqtrade.strategy import IStrategy, informative


class TrendGuard1h(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    startup_candle_count = 400
    process_only_new_candles = True

    # Provisional risk and exit parameters - to be evaluated, not optimized on a single period.
    stoploss = -0.04
    minimal_roi = {"0": 0.08, "1440": 0.05, "4320": 0.03}
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True
    use_exit_signal = True

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_4h = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
        )
        trend_1h = (
            (dataframe["close"] > dataframe["ema50"])
            & (dataframe["ema50"] > dataframe["ema200"])
            & (dataframe["ema50"] > dataframe["ema50"].shift(6))
        )
        pullback_recovery = (
            qtpylib.crossed_above(dataframe["rsi"], 46)
            & (dataframe["rsi"] < 64)
        )
        volatility_ok = (dataframe["atr_pct"] > 0) & (dataframe["atr_pct"] < 0.035)
        dataframe.loc[
            trend_4h & trend_1h & pullback_recovery & volatility_ok & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "4h_uptrend_1h_pullback")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_break = (
            ((dataframe["close"] < dataframe["ema50"]) & (dataframe["rsi"] < 43))
            | (dataframe["close_4h"] < dataframe["ema200_4h"])
        )
        dataframe.loc[trend_break & (dataframe["volume"] > 0), ["exit_long", "exit_tag"]] = (
            1,
            "trend_break",
        )
        return dataframe
