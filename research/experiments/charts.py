"""Charts for the report (matplotlib, PNG)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt

from common import *  # noqa
from e3_ensemble import build

BLUE, ORANGE, AQUA = "#257de0", "#f47230", "#00b894"
TXT, TXT2, GRID = "#191919", "#666666", "#e6e6e6"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": TXT2, "xtick.color": TXT2,
                     "ytick.color": TXT2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
SY = ["BTCUSDT", "ETHUSDT"]
start = "2018-03-01"
ls = build(SY, mode="ls_gated", vt=0.5)["equity"].loc[start:]
lo = build(SY, mode="long", vt=0.5)["equity"].loc[start:]
bh = combine([buy_hold(load_klines(s, "4h").loc[start:]) for s in SY])["equity"]
series = [("Trend-Ensemble L/S (Spot-Long + Perp-Short im Bärenmarkt)", ls, BLUE),
          ("Trend-Ensemble nur Long (Spot)", lo, AQUA),
          ("Buy & Hold 50/50 BTC+ETH", bh, ORANGE)]


def norm(s):
    s = daily(s)
    return 1000 * s / s.iloc[0]


def shade_periods(ax):
    for (a, b), lab in [(PERIODS["val"], "Validierung"), (PERIODS["hold"], "Holdout")]:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="#f2f2f2", zorder=0, lw=0)
        ax.text(pd.Timestamp(a) + pd.Timedelta(days=15), 0.98, lab, transform=ax.get_xaxis_transform(), va="top", color=TXT2, fontsize=9)


# 1) equity curves (log)
fig, ax = plt.subplots(figsize=(11, 5.5))
shade_periods(ax)
for name, s, col in series:
    n = norm(s)
    n.index = n.index.tz_localize(None)
    ax.plot(n.index, n.values, color=col, lw=2, label=name)
    ax.annotate(f"{n.iloc[-1]:,.0f}".replace(",", "."), (n.index[-1], n.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                color=TXT, fontsize=9, va="center")
ax.set_yscale("log")
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
ax.set_ylabel("Depotwert in USDT (Start 1.000, log)")
ax.set_title("Kapitalverlauf nach Kosten (0,15 %/Seite Spot, 0,10 %/Seite Perp, inkl. Funding)", loc="left", color=TXT)
ax.legend(loc="upper left", fontsize=9)
fig.tight_layout()
fig.savefig(RES / "chart_equity.png", dpi=150)

# 2) drawdown
fig, ax = plt.subplots(figsize=(11, 3.8))
shade_periods(ax)
for name, s, col in [series[0], series[2]]:
    d = daily(s)
    dd = 100 * (d / d.cummax() - 1)
    dd.index = dd.index.tz_localize(None)
    ax.plot(dd.index, dd.values, color=col, lw=1.6, label=name)
ax.set_ylabel("Drawdown in %")
ax.set_title("Rückgang vom letzten Höchststand", loc="left", color=TXT)
ax.legend(loc="lower left", fontsize=9)
fig.tight_layout()
fig.savefig(RES / "chart_drawdown.png", dpi=150)

# 3) yearly returns
y = pd.read_csv(RES / "e6_yearly.csv", index_col=0)
fig, ax = plt.subplots(figsize=(11, 4.2))
x = np.arange(len(y))
w = 0.38
ax.bar(x - w / 2 - 0.01, y["strategy_%"], w, color=BLUE, label="Trend-Ensemble L/S", edgecolor="white", linewidth=1)
ax.bar(x + w / 2 + 0.01, y["buyhold_5050_%"], w, color=ORANGE, label="Buy & Hold 50/50", edgecolor="white", linewidth=1)
ax.axhline(0, color=TXT2, lw=0.8)
ax.set_xticks(x, [str(i) for i in y.index])
ax.set_ylabel("Rendite im Kalenderjahr in %")
ax.set_title("Jahresrenditen (2018 ab Jan; 2026 bis 24.11.)", loc="left", color=TXT)
ax.legend(loc="upper right", fontsize=9)
fig.tight_layout()
fig.savefig(RES / "chart_yearly.png", dpi=150)
print("charts written")
