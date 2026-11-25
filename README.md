# Tradingbot – Quant-Research für den Freqtrade-Papertrading-Bot

Privates Forschungsprojekt. **Nur Papertrading (dry-run). Keine Secrets in diesem Repository.**

| Dokument | Inhalt |
|---|---|
| [`docs/PROJEKTSTAND.md`](docs/PROJEKTSTAND.md) | Einschätzung des tatsächlichen Projektstands, Schwachstellen, nächste Schritte |
| [`research/REPORT.md`](research/REPORT.md) | Forschungsbericht mit allen Ergebnissen (auch negativen) |
| [`research/RESEARCH_PROMPT.md`](research/RESEARCH_PROMPT.md) | Vorab festgelegter Forschungsauftrag und Methodik |
| [`freqtrade/README.md`](freqtrade/README.md) | Strategien, Backtest-Reproduktion, separater Dry-Run-Bot |

## Ergebnis in einem Satz

TrendGuard1h hat über 2018–2026 keinen Vorteil (−13,5 %); kurze Timeframes verlieren nach Kosten durchweg;
ein **Trend-Ensemble auf 4h mit Volatilitätssteuerung** (`TrendEnsembleSpot4h`) war in Entwicklung, Validierung
und Holdout positiv und robust – mit klaren Grenzen (schwach im Bärenmarkt, hinter Buy & Hold im Bullenmarkt).
Historische Ergebnisse sind keine Gewinnzusage.

## Struktur

```
research/
  scripts/       Download (data.binance.vision), Parquet-Cache, Export nach Freqtrade
  lib/           Daten, Indikatoren, Backtest-Engine, Kennzahlen
  experiments/   e1 … e8 (jede Zahl im Bericht stammt aus einem dieser Skripte), charts.py
  results/       CSV-Ergebnisse, Freqtrade-Ausgaben, Grafiken
freqtrade/
  user_data/strategies/   TrendEnsembleSpot4h, TrendEnsembleBearShort4h, TrendGuard1h (Original)
  user_data/config.*.json Konfigurationen ohne Secrets
  docker-compose.ensemble.yml
docs/PROJEKTSTAND.md
```
