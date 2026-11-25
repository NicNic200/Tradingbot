# Freqtrade: Forschungsstrategien und separater Papertrading-Bot

**Nur dry-run. Der bestehende TrendGuard1h-Bot wird durch nichts hier verändert.**

## Inhalt

| Datei | Zweck |
|---|---|
| `user_data/strategies/TrendEnsembleSpot4h.py` | Kandidat: Spot, Long-only, 4h, Trend-Ensemble + Vol-Target + Rebalancing |
| `user_data/strategies/TrendEnsembleBearShort4h.py` | Optionale Short-Komponente (Futures, 1x, nur Bärenregime) – nur Forschung |
| `user_data/strategies/TrendGuard1h.py` | Original (Referenz, unverändert) |
| `user_data/config.research.json` | Backtest-Config ohne Secrets (StaticPairList BTC/ETH) |
| `user_data/config.ensemble.json` | Backtest-Config für das Ensemble (`stake_amount: unlimited`) |
| `user_data/config.ensemble.futures.json` | Backtest-Config Futures (Short-Komponente) |
| `user_data/config.ensemble.paper.json` | Vorlage für den 2. Dry-Run-Bot – Platzhalter, **keine** Secrets |
| `docker-compose.ensemble.yml` | Eigenes Compose-Projekt für den 2. Bot (Port 8081, eigene DB) |
| `ft_offline.py` | Nur für die Cloud-Research-Umgebung (Binance-API dort gesperrt). **Auf dem Server nicht nötig.** |

## 1. Auf dem Server: Backtest reproduzieren (ändert nichts am laufenden Bot)

```bash
cd ~/trading-bot
# Repo holen (privat) – z. B. nach ~/Tradingbot-repo
git clone https://github.com/NicNic200/Tradingbot.git ~/Tradingbot-repo   # bzw. git pull
cp ~/Tradingbot-repo/freqtrade/user_data/strategies/TrendEnsembleSpot4h.py user_data/strategies/
cp ~/Tradingbot-repo/freqtrade/user_data/config.ensemble.json user_data/

# 4h-Daten ab 2017 laden (zusätzlich zu den vorhandenen 1h/4h-Daten ab 2023)
sudo docker compose run --rm freqtrade download-data \
  --config user_data/config.ensemble.json --timeframes 4h --timerange 20170801- \
  --pairs BTC/USDT ETH/USDT

sudo docker compose run --rm freqtrade list-strategies --config user_data/config.ensemble.json

sudo docker compose run --rm freqtrade backtesting \
  --config user_data/config.ensemble.json --strategy TrendEnsembleSpot4h --timeframe 4h \
  --pairs BTC/USDT ETH/USDT --max-open-trades 2 --dry-run-wallet 1000 --fee 0.0015 \
  --timerange 20180101-20261125 --breakdown year --cache none
```

Erwartung (Research-Lauf, Fee 0,15 %): ≈ 245 Trades, ≈ +690 %, CAGR ≈ 26,7 %, max. Wallet-Drawdown ≈ 23,9 %.
Kleine Abweichungen durch Datenstand/Präzision sind normal; große Abweichungen bitte melden.

Optional: `lookahead-analysis` und `recursive-analysis`:

```bash
sudo docker compose run --rm freqtrade lookahead-analysis --config user_data/config.ensemble.json \
  --strategy TrendEnsembleSpot4h --timeframe 4h --pairs BTC/USDT ETH/USDT --timerange 20240101-20251231
sudo docker compose run --rm freqtrade recursive-analysis --config user_data/config.ensemble.json \
  --strategy TrendEnsembleSpot4h --timeframe 4h --pairs BTC/USDT --timerange 20240101-20250101
```

## 2. Zweiter Dry-Run-Bot (erst nach deiner Freigabe)

1. Vorlage kopieren und **nur auf dem Server** ausfüllen (API-Benutzer/Passwort/JWT; optional Telegram):
   ```bash
   cp ~/Tradingbot-repo/freqtrade/user_data/config.ensemble.paper.json user_data/
   cp ~/Tradingbot-repo/freqtrade/docker-compose.ensemble.yml .
   nano user_data/config.ensemble.paper.json       # CHANGE_ME-Felder ersetzen
   python3 -m json.tool user_data/config.ensemble.paper.json > /dev/null && echo OK
   ```
   - **Telegram:** Nicht denselben Bot-Token wie TrendGuard1h verwenden (zwei Bots, die denselben Token abfragen,
     stören sich). Für Telegram einen zweiten Bot bei @BotFather anlegen, sonst `enabled: false` lassen.
   - `dry_run` bleibt `true`. Eigene DB: `tradesv3.ensemble.paper.sqlite`.
2. Starten (eigenes Compose-Projekt, berührt den bestehenden Container nicht):
   ```bash
   sudo docker compose -f docker-compose.ensemble.yml -p ensemble up -d
   sudo docker compose -f docker-compose.ensemble.yml -p ensemble logs --tail=60
   ```
3. FreqUI: `ssh -L 8081:127.0.0.1:8081 nicnic@<server>` → `http://localhost:8081`
4. Stoppen: `sudo docker compose -f docker-compose.ensemble.yml -p ensemble stop`

Ressourcen: ein zusätzlicher Freqtrade-Container braucht typischerweise einige hundert MB RAM – vorher mit
`free -h` in der VM prüfen. Beim Start lädt die Strategie 1.210 4h-Kerzen (Hinweis „Using 2 calls“ ist normal).

## 3. Was im Papertrading zu erwarten ist

- ≈ 28 Trades pro Jahr plus Teilkäufe/-verkäufe (Rebalancing). Wochen ohne Aktion sind normal.
- Trefferquote ~16 %: viele kleine Verluste, wenige große Gewinne. Seitwärtsphasen bis 1–2 Jahre ohne neues Hoch
  sind historisch vorgekommen.
- Sinnvoller Monatscheck: Dry-Run-Trades mit einem Backtest über denselben Zeitraum vergleichen
  (gleiche Einstiege/Ausstiege?). Bewertung der Profitabilität frühestens nach 6–12 Monaten.

## 4. Short-Komponente (später, optional)

`TrendEnsembleBearShort4h` braucht `trading_mode: futures`, `margin_mode: isolated`, eigene Config/DB/Port.
Vorher prüfen, ob Binance-Futures für dein Konto/Land verfügbar und zulässig sind. Nur dry-run.
