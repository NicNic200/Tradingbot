"""TrendEnsembleBearShort4h - research candidate (USDT-M futures, SHORT-only, 1x, dry-run only).

Short leg of the research portfolio "trend ensemble, long via spot / short via perp in bear regime":
    short when ensemble score < 0 AND close < 200-day SMA (bear regime); cover when either condition ends.
    size = |score| * min(1, 50% / realized 30d vol) * (equity / number of pairs), leverage 1x.
Intended to run as a SEPARATE dry-run bot next to TrendEnsembleSpot4h (own config, own DB, own port).

Research only. No live futures trading without separate review, legal/product availability check and
explicit approval.  Shorts have theoretically unlimited loss; funding is paid/received every 8h.
"""
from datetime import datetime

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

from TrendEnsembleSpot4h import BARS_PER_DAY, _donchian_state


class TrendEnsembleBearShort4h(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 1210

    minimal_roi = {"0": 100.0}
    stoploss = -0.25          # disaster stop (25 % adverse move on the position)
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False

    position_adjustment_enable = True
    max_entry_position_adjustment = -1

    vol_target = 0.50
    rebalance_band = 0.10

    def leverage(self, pair: str, current_time: datetime, current_rate: float, proposed_leverage: float,
                 max_leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        return 1.0

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
        dataframe["bear"] = (c < sma200).astype(int)
        vol = np.log(c).diff().rolling(30 * d).std() * np.sqrt(365 * d)
        dataframe["size"] = np.clip(self.vol_target / vol, 0.0, 1.0).fillna(0.0)
        dataframe["target"] = (-dataframe["score"]).clip(lower=0) * dataframe["size"] * dataframe["bear"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["target"] > 0.02) & (dataframe["volume"] > 0),
                      ["enter_short", "enter_tag"]] = (1, "bear_trend_ensemble")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[((dataframe["score"] >= 0) | (dataframe["bear"] == 0)) & (dataframe["volume"] > 0),
                      ["exit_short", "exit_tag"]] = (1, "bear_over")
        return dataframe

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
        reduce = min(-diff, current_value - (min_stake or 0) * 1.5)
        if reduce <= (min_stake or 0):
            return None
        return -reduce, "rebalance_down"
