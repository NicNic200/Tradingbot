# Projektstand und Schwachstellen (Einschätzung vom 25.11.2026)

Kennzeichnung: **[BELEGT]** = durch Übergabe/Logs belegt · **[HIER GEPRÜFT]** = in dieser Session unabhängig
nachgerechnet · **[OFFEN]** = nicht verifiziert.

## 1. Was tatsächlich vorliegt

| Bereich | Stand | Status |
|---|---|---|
| Proxmox → Debian 13 → Docker → Freqtrade 2026.10 | lief am 22.11.2026, Container `Up`, `RUNNING` | [BELEGT] |
| Papertrading-Bot `TrendGuard1h` | Spot, dry_run, BTC+ETH, 100 USDT/Trade, max. 2 Trades | [BELEGT], Live-Zustand am 25.11. [OFFEN] |
| Telegram + FreqUI (127.0.0.1:8080, SSH-Tunnel) | funktionierte | [BELEGT] |
| Restart-Policy `unless-stopped`, Proxmox-Autostart | empfohlen | [OFFEN] |
| Freqtrade-Protections | keine aktiv | [BELEGT] |
| TrendGuard1h-Backtests 2024–25 (+0,28 %) und 2026 (−2,31 %) | exakt reproduziert | [HIER GEPRÜFT] |
| TrendGuard1h 2018–2026 | −13,5 %, PF 0,78, 8/9 Jahre negativ | [HIER GEPRÜFT] |
| Codex-Ergebnisse 23.11. | Dateien nicht vorhanden, Repo war leer | [OFFEN] – nicht prüfbar |
| Profitable Strategie | bisher keine; neuer Kandidat siehe unten | – |

## 2. Schwachstellen (nach Priorität)

1. **Kein Handelsvorteil in TrendGuard1h.** Der Durchschnittstrade (−0,23 %) entspricht den Gebühren; das Signal
   ist brutto ≈ Zufall. Optimieren lohnt nicht – das wäre Kurvenanpassung an Rauschen.
2. **Falscher Zeithorizont.** 1h-Signale mit ~16 h Haltedauer handeln Rauschen; Kosten von 0,2–0,3 % je
   Round-Trip sind gemessen am Brutto-Vorteil zu hoch. Die Forschung zeigt: 5m/15m/1h-Strategien verlieren nach
   Kosten durchweg, erst Trendfolge über Tage–Wochen trägt.
3. **Positionsgröße verzerrt die Wahrnehmung.** 100 USDT je Trade bei 1.000 USDT (max. 20 % investiert) erzeugt
   kleine Drawdowns, aber auch kleine Erträge. „Geringer Drawdown“ war kein Qualitätsmerkmal.
4. **Statistisch zu kurze Bewertungsfenster.** 4 Wochen Papertrading mit ~5 Trades sagen nichts über
   Profitabilität; die Daten auf dem Server beginnen erst 2023 (ein Marktzyklus fehlt).
5. **Kostenmodell unvollständig.** Bisher `--fee 0.001` ohne Slippage. Hier: 0,15 %/Seite Basis, Stress bis 0,40 %.
6. **Keine In-/Out-of-Sample-Trennung** in den bisherigen Tests; 2024–2026 wurde mehrfach betrachtet.
7. **Betrieb:** Restart-Policy und VM-Autostart unbestätigt; keine Protections; Secrets liegen in `config.json`
   und Backups – dürfen nie ins Repo (siehe `.gitignore`).

## 3. Was in dieser Session gebaut wurde

- Reproduzierbare Datenpipeline (Binance-Archiv, 16 Coins, Spot + Perps + Funding, 2017–2026) mit Qualitätsprüfung.
- Zwei unabhängige Backtest-Wege (eigene konservative Engine + Original-Freqtrade), gegenseitig abgeglichen.
- ≈ 268 getestete Konfigurationen in 8 Experimenten mit fester Dev/Val/Holdout-Trennung, Walk-Forward,
  Kostenstress, Parameter-Plateaus, Cross-Asset-Test, Bootstrap und Deflated Sharpe Ratio.
- Neuer Kandidat **TrendEnsembleSpot4h** (Spot, Long-only) + optionale Short-Komponente
  **TrendEnsembleBearShort4h** (Futures, nur Forschung) als Freqtrade-Strategien, `lookahead-analysis` ohne Befund.
- Anleitung für einen **zweiten, getrennten** Dry-Run-Bot (`freqtrade/README.md`).

Details und alle Zahlen: [`research/REPORT.md`](../research/REPORT.md).

## 4. Nächste Schritte (ohne Risiko)

1. Auf dem Server prüfen (nur lesen): `sudo docker compose ps -a`, Logs, Restart-Policy.
2. Repo auf den Server holen, Strategie-Datei kopieren, 4h-Daten ab 2017 laden, Backtest reproduzieren.
3. Nach deiner Freigabe: zweiten Dry-Run-Bot `freqtrade-ensemble` starten (Port 8081, eigene DB). Der bestehende
   TrendGuard1h-Bot bleibt unverändert.
4. 6–12 Monate beobachten; monatlich Dry-Run-Trades gegen den Backtest desselben Zeitraums abgleichen.
5. Erst danach über eine Futures-Short-Komponente (dritter Dry-Run-Bot) entscheiden.
6. Codex-Dateien hochladen, falls sie noch geprüft werden sollen.
