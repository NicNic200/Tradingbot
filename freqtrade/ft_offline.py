"""Run the Freqtrade CLI offline (backtesting / lookahead-analysis only).

Why: The research container cannot reach api.binance.com (geo-restricted), but Freqtrade loads the
market definitions from the exchange at start-up.  This launcher injects static Binance spot market
definitions (precision / limits) for the pairs we use, everything else in Freqtrade is unchanged.
NOT needed (and not to be used) on the Proxmox server, where Freqtrade reaches Binance normally.

Usage:  python ft_offline.py backtesting --config ... (same arguments as `freqtrade`)
"""
import sys

from freqtrade.exchange import exchange as ft_exchange

BASES = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "DOT", "TRX", "ATOM",
         "XLM", "ETC", "BCH"]


def _markets():
    out = []
    for b in BASES:
        out.append({
            "id": f"{b}USDT", "symbol": f"{b}/USDT", "base": b, "quote": "USDT", "settle": None,
            "baseId": b, "quoteId": "USDT", "settleId": None, "type": "spot", "spot": True, "margin": False,
            "swap": False, "future": False, "option": False, "active": True, "contract": False,
            "linear": None, "inverse": None, "contractSize": None, "taker": 0.001, "maker": 0.001,
            "precision": {"amount": 1e-08, "price": 1e-08, "base": 1e-08, "quote": 1e-08},
            "limits": {"amount": {"min": 1e-08, "max": 1e9}, "price": {"min": 1e-08, "max": 1e9},
                       "cost": {"min": 5.0, "max": None}, "leverage": {"min": None, "max": None}},
            "info": {}, "created": None,
        })
        out.append({
            "id": f"{b}USDT", "symbol": f"{b}/USDT:USDT", "base": b, "quote": "USDT", "settle": "USDT",
            "baseId": b, "quoteId": "USDT", "settleId": "USDT", "type": "swap", "spot": False, "margin": False,
            "swap": True, "future": False, "option": False, "active": True, "contract": True,
            "linear": True, "inverse": False, "contractSize": 1.0, "taker": 0.0005, "maker": 0.0002,
            "precision": {"amount": 1e-08, "price": 1e-08, "base": 1e-08, "quote": 1e-08},
            "limits": {"amount": {"min": 1e-08, "max": 1e9}, "price": {"min": 1e-08, "max": 1e9},
                       "cost": {"min": 5.0, "max": None}, "leverage": {"min": 1, "max": 20}},
            "info": {}, "created": None,
        })
    return out


async def _offline_reload(self, reload: bool = False) -> None:
    self._api_async.set_markets(_markets())


ft_exchange.Exchange._api_reload_markets = _offline_reload
ft_exchange.Exchange.fetch_trading_fees = lambda self: {}

if __name__ == "__main__":
    from freqtrade.main import main
    sys.exit(main(sys.argv[1:]))
