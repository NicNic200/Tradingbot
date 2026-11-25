"""TrendEnsembleSpot4h - research candidate (spot, long-only, dry-run only).

Idea: instead of one optimized indicator, 11 standard trend "votes" (lookbacks fixed a priori, in days):
    SMA 20/50/100/200, Donchian 20/10 and 55/20, momentum 30/90/180, EMA cross 10/30 and 20/100.
    score = mean(votes) in [-1, 1]
Position per pair = max(score, 0) * min(1, 50% / realized 30d volatility) * (equity / number of pairs).
The position is adjusted (partial buy / partial sell) when it deviates from its target by > 10% of the
pair's capital share; it is closed when score <= 0.

Research results (see research/REPORT.md) are historical backtests, NOT a profit guarantee.
Not for live trading without separate review and explicit approval.
"""
from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

BARS_PER_DAY = 6  # 4h candles


def _donchian_state(df: DataFrame, ne: int, nx: int) -> np.ndarray:
    c = df["close"].to_numpy()
    hi_e = df["high"].rolling(ne).max().shift(1).to_numpy()
    lo_e = df["low"].rolling(ne).min().shift(1).to_numpy()
    hi_x = df["high"].rolling(nx).max().shift(1).to_numpy()
    lo_x = df["low"].rolling(nx).min().shift(1).to_numpy()
    st = np.zeros(len(c))
    cur = 0
    for i in range(len(c)):
        if cur == 1 and c[i] < lo_x[i]:
            cur = 0
        if cur == -1 and c[i] > hi_x[i]:
            cur = 0
        if cur == 0 and c[i] > hi_e[i]:
            cur = 1
        elif cur == 0 and c[i] < lo_e[i]:
            cur = -1
        st[i] = cur
    return st


class TrendEnsembleSpot4h(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 1210  # 200 days of 4h candles + margin

    # exits are driven by the ensemble score; ROI disabled; wide disaster stop only
    minimal_roi = {"0": 100.0}
    stoploss = -0.25
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    position_adjustment_enable = True
    max_entry_position_adjustment = -1

    vol_target = 0.50     # annualized
    rebalance_band = 0.10  # fraction of the pair's capital share

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        c = dataframe["close"]
        d = BARS_PER_DAY
        votes = []
        for n in (20, 50, 100, 200):
            votes.append(np.sign(c - c.rolling(n * d).mean()))
        for ne, nx in ((20, 10), (55, 20)):
            votes.append(pd.Series(_donchian_state(dataframe, ne * d, nx * d), index=dataframe.index))
        for lb in (30, 90, 180):
            votes.append(np.sign(c / c.shift(lb * d) - 1))
        for f, s in ((10, 30), (20, 100)):
            votes.append(np.sign(ta.EMA(dataframe, timeperiod=f * d) - ta.EMA(dataframe, timeperiod=s * d)))
        v = pd.concat(votes, axis=1)
        sma200 = c.rolling(200 * d).mean()
        ready = v.notna().all(axis=1) & sma200.notna()
        dataframe["score"] = v.fillna(0).mean(axis=1).where(ready, 0.0)
        logret = np.log(c).diff()
        vol = logret.rolling(30 * d).std() * np.sqrt(365 * d)
        dataframe["size"] = np.clip(self.vol_target / vol, 0.0, 1.0).fillna(0.0)
        dataframe["target"] = dataframe["score"].clip(lower=0) * dataframe["size"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["score"] > 0) & (dataframe["target"] > 0.02) & (dataframe["volume"] > 0),
                      ["enter_long", "enter_tag"]] = (1, "trend_ensemble")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["score"] <= 0) & (dataframe["volume"] > 0), ["exit_long", "exit_tag"]] = (1, "score_flat")
        return dataframe

    # ---------- sizing helpers
    def _pair_capital(self) -> float:
        n = max(1, len(self.dp.current_whitelist()))
        return self.wallets.get_total_stake_amount() / n

    def _target(self, pair: str) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return 0.0
        return float(df["target"].iat[-1])

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        stake = self._target(pair) * self._pair_capital()
        if min_stake and stake < min_stake:
            return 0.0
        return min(stake, max_stake)

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float,
                              current_profit: float, min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float, **kwargs):
        if trade.has_open_orders:
            return None
        cap = self._pair_capital()
        target_stake = self._target(trade.pair) * cap
        current_value = trade.amount * current_rate
        diff = target_stake - current_value
        if abs(diff) <= self.rebalance_band * cap:
            return None
        if diff > 0:
            if min_stake and diff < min_stake:
                return None
            return min(diff, max_stake), "rebalance_up"
        # partial exit: never sell the whole position via adjustment (exit signal does that)
        reduce = min(-diff, current_value - (min_stake or 0) * 1.5)
        if reduce <= (min_stake or 0):
            return None
        return -reduce, "rebalance_down"
