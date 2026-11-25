"""Conservative bar-based backtest engines.

Conventions (identical for all experiments):
* Signals are computed on the CLOSE of bar t and executed at the OPEN of bar t+1.
* Stops are checked intrabar via high/low.  A gap through the stop fills at the (worse) open.
* If stop and take-profit are both touched in the same bar the STOP is assumed first.
* Trailing stops are updated with highs/lows of *completed* bars only (no intrabar optimism).
* `cost` is charged per side as a fraction of notional (fee + slippage).
* Funding (perpetual futures): longs pay `rate * notional`, shorts receive it, at each settlement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

# exit reason codes
R_SIGNAL, R_STOP, R_TRAIL, R_TP, R_TIME, R_END = 0, 1, 2, 3, 4, 5
REASONS = {0: "signal", 1: "stop", 2: "trail", 3: "tp", 4: "time", 5: "end"}


@njit(cache=True)
def _run(o, h, l, c, ent, ext, direction, stop_d, trail_d, tp_d, max_bars, size, cost, funding, allow_reentry_same_bar):
    n = len(o)
    eq = np.empty(n)
    expo = np.zeros(n)
    tr = np.zeros((n, 9))  # entry_i, exit_i, dir, entry_px, exit_px, ret_net, reason, size, mfe
    nt = 0
    equity = 1.0
    pos = 0  # +1 long, -1 short
    qty_val = 0.0  # notional at entry (in equity units)
    entry_px = 0.0
    stop_px = 0.0
    tp_px = 0.0
    trail = 0.0
    best = 0.0
    eq_entry = 0.0
    entry_i = 0
    fund_acc = 0.0
    for i in range(n):
        if i == 0:
            eq[i] = equity
            continue
        exited = False
        if pos != 0:
            # ---- funding at bar open
            if funding[i] != 0.0:
                notional = qty_val * o[i] / entry_px
                fund_acc -= pos * funding[i] * notional
            px = 0.0
            reason = -1
            # ---- decisions made at close of i-1, executed at open i
            if ext[i - 1] == pos:
                px = o[i]; reason = R_SIGNAL
            elif max_bars > 0 and (i - entry_i) >= max_bars:
                px = o[i]; reason = R_TIME
            else:
                # effective stop = tighter of initial stop and trailing stop
                eff = stop_px
                rs = R_STOP
                if trail > 0.0:
                    if pos == 1:
                        t = best - trail
                        if t > eff:
                            eff = t; rs = R_TRAIL
                    else:
                        t = best + trail
                        if eff == 0.0 or t < eff:
                            eff = t; rs = R_TRAIL
                if pos == 1:
                    if eff > 0.0 and o[i] <= eff:
                        px = o[i]; reason = rs
                    elif eff > 0.0 and l[i] <= eff:
                        px = eff; reason = rs
                    elif tp_px > 0.0 and o[i] >= tp_px:
                        px = o[i]; reason = R_TP
                    elif tp_px > 0.0 and h[i] >= tp_px:
                        px = tp_px; reason = R_TP
                else:
                    if eff > 0.0 and o[i] >= eff:
                        px = o[i]; reason = rs
                    elif eff > 0.0 and h[i] >= eff:
                        px = eff; reason = rs
                    elif tp_px > 0.0 and o[i] <= tp_px:
                        px = o[i]; reason = R_TP
                    elif tp_px > 0.0 and l[i] <= tp_px:
                        px = tp_px; reason = R_TP
            if reason >= 0:
                gross = pos * (px / entry_px - 1.0)
                pnl = qty_val * gross - qty_val * cost - qty_val * (px / entry_px) * cost + fund_acc
                equity = eq_entry + pnl
                tr[nt, 0] = entry_i; tr[nt, 1] = i; tr[nt, 2] = pos; tr[nt, 3] = entry_px; tr[nt, 4] = px
                tr[nt, 5] = pnl / qty_val if qty_val > 0 else 0.0
                tr[nt, 6] = reason; tr[nt, 7] = qty_val / eq_entry
                tr[nt, 8] = pos * (best / entry_px - 1.0)
                nt += 1
                pos = 0
                exited = True
        # ---- entries (signal at close i-1 -> open i)
        if pos == 0 and (not exited or allow_reentry_same_bar) and ent[i - 1] != 0 and (direction == 0 or ent[i - 1] == direction):
            d = ent[i - 1]
            s = size[i - 1]
            if s > 0.0 and not np.isnan(s):
                pos = d
                entry_px = o[i]
                entry_i = i
                eq_entry = equity
                qty_val = equity * s
                fund_acc = 0.0
                sd = stop_d[i - 1]
                stop_px = entry_px * (1.0 - d * sd) if sd > 0.0 else 0.0
                td = tp_d[i - 1]
                tp_px = entry_px * (1.0 + d * td) if td > 0.0 else 0.0
                trail = trail_d[i - 1] * entry_px if trail_d[i - 1] > 0.0 else 0.0
                best = entry_px
                # same-bar stop check (entry at open, stop can be hit within the bar)
                if stop_px > 0.0 and ((d == 1 and l[i] <= stop_px) or (d == -1 and h[i] >= stop_px)):
                    px = stop_px
                    gross = d * (px / entry_px - 1.0)
                    pnl = qty_val * gross - qty_val * cost - qty_val * (px / entry_px) * cost
                    equity = eq_entry + pnl
                    tr[nt, 0] = entry_i; tr[nt, 1] = i; tr[nt, 2] = d; tr[nt, 3] = entry_px; tr[nt, 4] = px
                    tr[nt, 5] = pnl / qty_val; tr[nt, 6] = R_STOP; tr[nt, 7] = s; tr[nt, 8] = 0.0
                    nt += 1
                    pos = 0
        # ---- mark to market at close, update trailing reference with the completed bar
        if pos != 0:
            if pos == 1:
                if h[i] > best:
                    best = h[i]
            else:
                if l[i] < best:
                    best = l[i]
            gross = pos * (c[i] / entry_px - 1.0)
            eq[i] = eq_entry + qty_val * gross - qty_val * cost + fund_acc
            expo[i] = pos * qty_val * (c[i] / entry_px) / max(eq[i], 1e-12)
        else:
            eq[i] = equity
    # close open position at the end (mark only, record as 'end')
    if pos != 0:
        px = c[n - 1]
        gross = pos * (px / entry_px - 1.0)
        pnl = qty_val * gross - qty_val * cost - qty_val * (px / entry_px) * cost + fund_acc
        tr[nt, 0] = entry_i; tr[nt, 1] = n - 1; tr[nt, 2] = pos; tr[nt, 3] = entry_px; tr[nt, 4] = px
        tr[nt, 5] = pnl / qty_val; tr[nt, 6] = R_END; tr[nt, 7] = qty_val / eq_entry; tr[nt, 8] = pos * (best / entry_px - 1.0)
        nt += 1
        eq[n - 1] = eq_entry + pnl
    return eq, expo, tr[:nt]


def _arr(x, n, default=0.0):
    if x is None:
        return np.full(n, default)
    if np.isscalar(x):
        return np.full(n, float(x))
    a = np.asarray(x, dtype=float)
    return np.nan_to_num(a, nan=0.0)


def run_trades(df: pd.DataFrame, entries, exits=None, direction: int = 1, stop=None, trail=None, tp=None,
               max_bars: int = 0, size=1.0, cost: float = 0.0015, funding=None, reentry_same_bar=False):
    """Single-asset trade backtest.

    entries/exits: arrays with +1 (long), -1 (short), 0.  For long-only pass booleans.
    stop/trail/tp: distance as fraction of entry price (scalar or per-bar array evaluated at signal bar).
    size: fraction of current equity allocated per trade (scalar or array).
    Returns dict(equity: Series, exposure: Series, trades: DataFrame).
    """
    n = len(df)
    ent = np.asarray(entries).astype(np.int64) if entries is not None else np.zeros(n, np.int64)
    if ent.dtype == bool or ent.max() <= 1 and direction == -1:
        ent = ent * direction
    ext = np.zeros(n, np.int64) if exits is None else np.asarray(exits).astype(np.int64)
    if exits is not None and direction == -1 and ext.min() >= 0:
        ext = -ext
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    eq, expo, tr = _run(o, h, l, c, ent, ext, direction, _arr(stop, n), _arr(trail, n), _arr(tp, n), max_bars,
                        _arr(size, n, 1.0), cost, _arr(funding, n), reentry_same_bar)
    idx = df.index
    trades = pd.DataFrame(tr, columns=["entry_i", "exit_i", "dir", "entry_px", "exit_px", "ret", "reason", "size", "mfe"])
    if len(trades):
        trades["entry_time"] = idx[trades["entry_i"].astype(int)]
        trades["exit_time"] = idx[trades["exit_i"].astype(int)]
        trades["bars"] = trades["exit_i"] - trades["entry_i"]
        trades["reason"] = trades["reason"].astype(int).map(REASONS)
    return {"equity": pd.Series(eq, idx), "exposure": pd.Series(expo, idx), "trades": trades}


def run_weights(prices_open: pd.DataFrame, weights: pd.DataFrame, cost=0.0015, funding: pd.DataFrame | None = None, band: float = 0.0):
    """Portfolio backtest from target weights.

    weights.loc[t] is decided with information up to the CLOSE of bar t and executed at OPEN of t+1.
    Returns are open-to-open.  Weights drift between rebalances; turnover is charged `cost` per unit.
    Negative weights = short (perp); funding (rate per bar, aligned to bar open) charged on notional.
    """
    w = weights.reindex(prices_open.index).fillna(0.0).shift(1).fillna(0.0)  # executed at open t
    r = prices_open.shift(-1) / prices_open - 1.0  # open t -> open t+1
    r = r.fillna(0.0)
    cols = prices_open.columns
    W = w[cols].to_numpy()
    R = r[cols].to_numpy()
    F = np.zeros_like(R) if funding is None else funding.reindex(prices_open.index)[cols].fillna(0.0).to_numpy()
    n, k = W.shape
    C = np.array([cost[c] for c in cols]) if isinstance(cost, dict) else np.full(k, float(cost))
    eq = np.empty(n)
    to = np.zeros(n)
    equity = 1.0
    cur = np.zeros(k)  # current drifted weights
    for t in range(n):
        tgt = W[t]
        # rebalance only when target changes materially (avoids paying for drift noise)
        if band > 0:
            # band rebalancing: trade an asset only if its weight deviates > band, or target goes flat/flips
            dev = np.abs(tgt - cur)
            need = (dev > band) | ((tgt == 0) & (cur != 0)) | (np.sign(tgt) != np.sign(cur))
            need &= dev > 1e-9
        else:
            need = (np.abs(tgt - cur) > 1e-9) & ((t == 0) or np.any(np.abs(W[t] - W[t - 1]) > 1e-9))
        if np.any(need):
            new_w = np.where(need, tgt, cur)
            turn_vec = np.abs(new_w - cur)
            equity *= (1.0 - (turn_vec * C).sum())
            to[t] = turn_vec.sum()
            cur = new_w
        # funding at open of t (longs pay, shorts receive)
        equity *= (1.0 - (cur * F[t]).sum())
        port_r = (cur * R[t]).sum()
        new_eq = equity * (1.0 + port_r)
        gross = cur * (1.0 + R[t])
        denom = 1.0 + port_r
        cur = gross / denom if denom > 0 else cur
        # short weights: drift sign stays, magnitude changes consistently with value of short leg
        equity = new_eq
        # equity is marked at open t+1 -> store at index t+1 conceptually; we store at t (open->open period)
        eq[t] = equity
    eqs = pd.Series(eq, prices_open.index).shift(1).fillna(1.0)
    expo = pd.Series(np.abs(W).sum(1), prices_open.index)
    return {"equity": eqs, "exposure": expo, "turnover": pd.Series(to, prices_open.index)}
