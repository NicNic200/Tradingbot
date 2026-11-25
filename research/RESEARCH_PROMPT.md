# Forschungsauftrag (Selbst-Prompt) — Quant-Research für den Freqtrade-Bot

> Dieser Prompt wurde zu Beginn der Session am 25.11.2026 geschrieben und **vor** dem Ansehen
> irgendwelcher Ergebnisse festgelegt. Er ist der verbindliche Rahmen für die Arbeit. Abweichungen
> werden im Bericht dokumentiert.

## Rolle und Ziel

Du bist ein skeptischer quantitativer Researcher. Ziel ist **nicht** die schönste Backtest-Kurve,
sondern eine Strategie, die nach realistischen Kosten mit hoher Wahrscheinlichkeit einen echten,
übertragbaren Vorteil hat — oder die ehrliche Aussage, dass keine gefunden wurde.
Arbeite ohne Rückfragen, so lange es geht (Zeitbudget ca. 5 h), dokumentiere alles reproduzierbar.

## Harte Regeln

1. Keine echten Orders, keine API-Keys, kein `dry_run=false`. Der laufende Bot `TrendGuard1h`
   auf dem Proxmox-Server wird **nicht** angefasst (er ist von hier aus ohnehin nicht erreichbar).
2. Keine Secrets in Dateien/Git. Beispielkonfigurationen enthalten nur Platzhalter.
3. Keine erfundenen Zahlen. Jede Zahl im Bericht stammt aus einem Skript in diesem Repo.
4. Negative Ergebnisse werden genauso berichtet wie positive.

## Daten

- Quelle: öffentliches Binance-Archiv `data.binance.vision` (Spot-Klines 1h/15m/5m,
  USDT-M-Futures-Klines 1h, Funding-Raten). Zeitraum so lang wie verfügbar (BTC/ETH ab 2017-08).
- Qualitätsprüfung: Duplikate, Lücken, Zeitstempel-Format (Binance wechselte 2025 auf µs),
  Null-Volumen-Kerzen, Ausreißer.
- Bias offen benennen: Das Coin-Universum ist aus heutiger Sicht gewählt (Survivorship-Bias).

## Methodik (vor Ergebnissen festgelegt)

**Zeitliche Aufteilung**

| Abschnitt | Zeitraum | Verwendung |
|---|---|---|
| Entwicklung (In-Sample) | 2018-01-01 – 2022-12-31 | Ideen, Parameter-Raster, Auswahl |
| Validierung | 2023-01-01 – 2024-12-31 | Bestätigung / Aussortieren, kein Feintuning |
| Holdout | 2025-01-01 – 2026-11-24 | einmalige Schlussprüfung der finalen Kandidaten |

Hinweis: 2024–2026 wurde vom Nutzer bereits mit TrendGuard1h/EMA_RSI_1h betrachtet; für die
*neuen* Strategien ist der Holdout trotzdem unberührt, weil Parameter nur auf 2018–2022 gewählt werden.

Zusätzlich: **Walk-Forward** (rollierend: Parameterwahl auf vorherigen 3 Jahren, Test auf den
nächsten 6 Monaten, aneinandergehängte OOS-Kurve) für die Finalisten.

**Ausführungs- und Kostenmodell**

- Signal auf Schlusskurs von Kerze *t*, Ausführung zum **Eröffnungskurs von *t+1*** (kein Lookahead).
- Stops intrabar über High/Low; bei Gap Ausführung zum (schlechteren) Open; wenn Stop und Ziel in
  derselben Kerze möglich sind, wird **zuerst der Stop** angenommen (konservativ).
- Kosten Basisszenario: 0,10 % Gebühr + 0,05 % Slippage **je Seite** (= 0,30 % Round-Trip).
  Stressszenario: 0,10 % + 0,15 % je Seite (= 0,50 % Round-Trip).
- Futures/Shorts: zusätzlich historische Funding-Raten, 1x Hebel, nur Forschung.

**Strategiefamilien (jeweils wenige, ökonomisch begründete Varianten)**

1. Baseline-Reproduktion von `TrendGuard1h` (Engine-Validierung gegen die bekannten Freqtrade-Werte).
2. Zeitreihen-Momentum / Trendfolge (gleitende Durchschnitte, Donchian-Breakout) auf 4h/1d.
3. Volatilitätsgesteuerte Positionsgröße (Volatility Targeting) als Risikobaustein.
4. Cross-Sectional-Momentum-Rotation über mehrere Coins mit BTC-Regimefilter.
5. Mean Reversion (RSI(2)/Bollinger) nur im übergeordneten Aufwärtstrend, 1h/15m.
6. Kurzfristige Breakouts auf 5m/15m — Test, ob nach Kosten überhaupt etwas übrig bleibt.
7. Long/Short-Trendfolge auf Perpetual-Futures inkl. Funding (nur simuliert, 1x).

**Robustheit / Overfitting-Schutz**

- Parameter-Raster statt Punktoptimierung; Auswahl aus einem stabilen **Plateau**, nicht der Spitze.
- Anzahl getesteter Konfigurationen protokollieren; Deflated Sharpe Ratio (Bailey/López de Prado).
- Übertragbarkeit: auf BTC/ETH gewählte Parameter **unverändert** auf 14 weiteren Coins testen.
- Kostenstress, Bootstrap-Konfidenzintervalle, Ergebnisse je Jahr und Marktregime.
- Vergleich mit Buy & Hold (BTC, ETH, 50/50) und Cash, unter Berücksichtigung der Exposure.

**Kennzahlen**

CAGR, Gesamtrendite, Max Drawdown (+ Dauer), Sharpe, Sortino, Calmar, Profit Factor,
Trefferquote, Expectancy pro Trade, Trades/Jahr, Exposure, Gebührenanteil.

**Akzeptanzkriterien für einen Kandidaten**

1. Positiv in Entwicklung **und** Validierung **und** Holdout nach Basiskosten.
2. Nach Stresskosten im Gesamtzeitraum nicht negativ.
3. Parameter-Nachbarschaft überwiegend profitabel (kein Nadelspitzen-Optimum).
4. Auf der Mehrheit der Fremd-Coins ohne Retuning positiv.
5. Max Drawdown deutlich unter Buy & Hold.

## Lieferumfang

1. `docs/PROJEKTSTAND.md` — Einschätzung des tatsächlichen Projektstands und Schwachstellen.
2. `research/` — Downloader, Backtest-Engine, Experimente, CSV-Ergebnisse, Grafiken.
3. `research/REPORT.md` — Forschungsbericht (Deutsch) mit allen Ergebnissen, auch negativen.
4. `freqtrade/` — finale Kandidaten als Freqtrade-Strategien + Research-Config ohne Secrets +
   Anleitung für einen **zweiten, getrennten** Papertrading-Bot (eigener Port, eigene DB).
5. Nach Möglichkeit Gegenprüfung der Kandidaten mit echtem Freqtrade-Backtesting
   und `lookahead-analysis`.
