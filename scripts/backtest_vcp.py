#!/usr/bin/env python3
"""
backtest_vcp.py — Point-in-time backtest comparing three EXIT rule-sets for a
Minervini VCP / momentum-breakout swing entry on NSE (Nifty 500) stocks.

Entries are IDENTICAL across rule-sets (paired comparison); only exits differ.

RULESET A ("jot"):      hard SL 7% below entry; full exit at 2R target;
                        20-trading-day time stop; entry-day EOD close < SL -> exit at close.
RULESET B ("w-bonkers"): SL 7% (same, for comparability); trend-broken EOD exit =
                        close < SMA50 AND close < SMA200 AND RSI(14) < 45 AND
                        MACD(12,26,9) histogram < 0; trim HALF at close the first
                        time RSI(14) > 80; no time stop (open positions force-closed
                        at end of data and counted).
HYBRID C:               SL 7%; book HALF at 2R level; remainder trails with B's
                        trend-broken exit; 30-trading-day time stop on the remainder.

Method / honesty notes (all decisions documented here and in RESULTS.md):
- Universe: current Nifty 500 membership (survivorship bias — OK for RELATIVE
  ruleset comparison, not for absolute return claims).
- Data: yfinance daily OHLCV, auto-adjusted, 2022-01-01 .. 2026-07-03.
  Cached per-ticker under backtest/cache/. Failed tickers skipped and counted.
  Tickers with any |1-day close move| > 50% are excluded as data-suspect
  (adjustment artifacts; NSE circuit limits make genuine >50% daily moves
  implausible) and counted.
- Signals: last NSEI trading day of each month 2023-07 .. 2026-05, using only
  data <= that day (all indicators are trailing-window computations read at the
  signal row — no lookahead).
- Stage-2 template: close > SMA50 > SMA150 > SMA200; SMA200 > SMA200 21 trading
  days ago; close >= 1.25 x 52w-low (rolling 252d min of Low); close <= within
  25% of 52w-high (close >= 0.75 x rolling 252d max of High); 12m (252 td)
  return > 12m ^NSEI return.
- Contraction: (15d max High - 15d min Low)/close < 0.10 AND that 15d range <
  the range of the prior 30d window (days D-44..D-15). Volume dry-up: 10d avg
  vol < 0.8 x 50d avg vol.
- Liquidity: 20d median turnover (Close x Volume, adjusted) >= Rs 5 crore.
- Pivot = 15d max High (incl. signal day). Entry: first of the next 20 trading
  days with High >= pivot*1.001; fill = max(Open, pivot*1.005) — i.e. 0.4%
  slippage above the trigger, but if the day gaps open above the fill level we
  fill at the open (no fantasy fills below the open). No trigger in 20 td ->
  signal expired (counted).
- Signal dedup: after a signal for a ticker (entered or expired), further
  signals for the same ticker are skipped until 20 trading days after the entry
  (or after the expired window). Keeps the entry list identical across
  rule-sets; a long-holding ruleset (B) may still hold when a later entry for
  the same ticker fires — affects book concurrency only, not paired stats.
- Exit day-ordering (each trading day after entry): (1) gap-open through SL ->
  exit remainder at Open; (2) intraday Low <= SL -> exit at SL level. SL WINS
  when SL and a target/trim level are both touchable the same day (conservative,
  stated in spec). (3) level targets (2R) fill AT the level (conservative on
  gap-ups); (4) indicator exits (trend-broken, RSI>80 trim) evaluated on EOD
  values, filled at Close; (5) time stops fill at Close of the Nth trading day
  after entry. Entry day itself: only the EOD "close < SL -> exit at close"
  check runs (intraday extremes on the breakout day are polluted by pre-entry
  trading); indicator/level exits start the next day. Same convention for all
  three rule-sets.
- Costs: 0.30% round trip per completed trade, split across legs: 0.15% of
  entry notional + 0.15% of each exit leg's notional.
- Rs 10,000 notional per trade, fractional shares. R = 7% of notional.
- Regime split: ^NSEI close vs its SMA200 on the ENTRY date.
- Book: equal-weight Rs 10k/trade, no compounding; daily mark-to-market equity;
  capital base = Rs 10k x (max concurrent open positions across ALL rule-sets)
  so total-return/DD denominators are comparable.
- Runtime guard: if the projected download time exceeds the budget (default 20
  min), the universe is cut to the first 250 symbols alphabetically and this is
  reported loudly.

Outputs: backtest/results{tag}.json, backtest/trades{tag}_{A,B,C}.csv,
console summary. RESULTS.md is written separately from results.json.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance not installed. Run: pip3 install --user yfinance")

# ---------------------------------------------------------------------------
# Paths / configuration
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKTEST_DIR = os.path.join(ROOT, "backtest")
CACHE_DIR = os.path.join(BACKTEST_DIR, "cache")
UNIVERSE_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
UNIVERSE_DEFAULT = os.path.join(BACKTEST_DIR, "universe_nifty500.csv")
EVALUATOR = os.path.expanduser(
    "~/.claude/skills/backtest-expert/scripts/evaluate_backtest.py")


def resolve_universe(path_arg):
    """Universe CSV: explicit --universe path > cached default > download the official list."""
    if path_arg:
        return path_arg
    if not os.path.exists(UNIVERSE_DEFAULT):
        import urllib.request
        req = urllib.request.Request(UNIVERSE_URL, headers={"User-Agent": "Mozilla/5.0"})
        os.makedirs(BACKTEST_DIR, exist_ok=True)
        with urllib.request.urlopen(req, timeout=30) as r, open(UNIVERSE_DEFAULT, "wb") as f:
            f.write(r.read())
    return UNIVERSE_DEFAULT

CFG = dict(
    data_start="2022-01-01",
    data_end="2026-07-04",            # exclusive-ish; includes 2026-07-03
    signal_month_start="2023-07",
    signal_month_end="2026-05",
    sl_pct=0.07,                      # hard stop 7% below entry
    r_multiple_target=2.0,            # 2R target (A full, C half)
    trigger_mult=1.001,               # breakout trigger above pivot
    fill_mult=1.005,                  # entry fill incl. slippage
    entry_window_td=20,               # trading days to trigger, else expired
    time_stop_a=20,                   # trading days (ruleset A)
    time_stop_c=30,                   # trading days (ruleset C remainder)
    cost_per_leg=0.0015,              # 0.15% per leg => 0.30% round trip
    notional=10000.0,                 # Rs per trade
    min_turnover=5e7,                 # Rs 5 crore, 20d median
    contraction_max=0.10,             # 15d range / close
    dryup_mult=0.8,                   # vol10 < 0.8*vol50
    low52_mult=1.25,
    high52_mult=0.75,
    batch_size=50,
    max_daily_move=0.50,              # data-suspect exclusion threshold
)

RULESETS = ["A_jot", "B_wbonkers", "C_hybrid"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
def cache_path(symbol):
    return os.path.join(CACHE_DIR, symbol.replace("^", "_") + ".pkl")


def clean_frame(df):
    """Normalize a yfinance frame: tz-naive daily index, OHLCV columns, sane rows."""
    if df is None or len(df) == 0:
        return None
    df = df.copy()
    # Flatten possible MultiIndex columns (single-ticker downloads)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    cols = {c.title(): c for c in map(str, df.columns)}
    need = ["Open", "High", "Low", "Close", "Volume"]
    if not all(k in [str(c).title() for c in df.columns] for k in need):
        return None
    df.columns = [str(c).title() for c in df.columns]
    df = df[need]
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["Close"] > 0) & (df["High"] >= df["Low"])]
    df["Volume"] = df["Volume"].fillna(0.0)
    return df if len(df) else None


def download_batch(symbols):
    """One yf.download call for a batch; returns {symbol: cleaned df or None}."""
    out = {}
    try:
        raw = yf.download(symbols, start=CFG["data_start"], end=CFG["data_end"],
                          auto_adjust=True, group_by="ticker", threads=True,
                          progress=False)
    except Exception as e:
        log(f"    batch download error: {e}")
        return {s: None for s in symbols}
    if raw is None or len(raw) == 0:
        return {s: None for s in symbols}
    if len(symbols) == 1:
        out[symbols[0]] = clean_frame(raw)
        return out
    for s in symbols:
        try:
            if isinstance(raw.columns, pd.MultiIndex) and s in set(raw.columns.get_level_values(0)):
                out[s] = clean_frame(raw[s])
            else:
                out[s] = None
        except Exception:
            out[s] = None
    return out


def fetch_universe(symbols, budget_sec):
    """Cache-first download with runtime guard. Returns (data, stats, truncated)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    failed_path = os.path.join(CACHE_DIR, "failed.json")
    prior_failed = set()
    if os.path.exists(failed_path):
        try:
            prior_failed = set(json.load(open(failed_path)))
        except Exception:
            prior_failed = set()

    data, cached, to_get, failed = {}, 0, [], set()
    for s in symbols:
        p = cache_path(s)
        if os.path.exists(p):
            try:
                data[s] = pd.read_pickle(p)
                cached += 1
                continue
            except Exception:
                pass
        if s in prior_failed:
            failed.add(s)
            continue
        to_get.append(s)

    log(f"universe: {len(symbols)} symbols | cache hits: {cached} | "
        f"known-failed skipped: {len(failed)} | to download: {len(to_get)}")

    truncated = False
    t0 = time.time()
    bs = CFG["batch_size"]
    i = 0
    while i < len(to_get):
        if i > 0:
            elapsed = time.time() - t0
            projected = elapsed * len(to_get) / i
            if projected > budget_sec and not truncated:
                keep = set(sorted(symbols)[:250])
                before = len(to_get)
                to_get = [s for s in to_get[:i]] + [s for s in to_get[i:] if s in keep]
                truncated = True
                log(f"!! RUNTIME GUARD: projected download {projected/60:.1f} min > "
                    f"{budget_sec/60:.0f} min budget — universe CUT to first 250 "
                    f"alphabetical symbols (pending downloads {before-i} -> {len(to_get)-i})")
        batch = to_get[i:i + bs]
        if not batch:
            break
        res = download_batch(batch)
        got = 0
        for s, df in res.items():
            if df is not None and len(df) > 0:
                df.to_pickle(cache_path(s))
                data[s] = df
                got += 1
            else:
                failed.add(s)
        i += len(batch)
        log(f"  downloaded batch {i}/{len(to_get)} (+{got}/{len(batch)} ok, "
            f"{time.time()-t0:.0f}s elapsed)")
        time.sleep(0.3)

    # one retry pass for freshly failed, individually
    retry = [s for s in failed if s not in prior_failed]
    if retry:
        log(f"retrying {len(retry)} failed tickers individually...")
        recovered = 0
        for s in retry:
            res = download_batch([s])
            df = res.get(s)
            if df is not None and len(df) > 0:
                df.to_pickle(cache_path(s))
                data[s] = df
                failed.discard(s)
                recovered += 1
            time.sleep(0.2)
        log(f"  recovered {recovered}/{len(retry)}")

    try:
        json.dump(sorted(failed), open(failed_path, "w"))
    except Exception:
        pass

    if truncated:
        keep = set(sorted(symbols)[:250])
        data = {s: df for s, df in data.items() if s in keep}

    stats = dict(universe_size=len(symbols), cache_hits=cached,
                 failed_download=len(failed), downloaded=len(data) - cached)
    return data, stats, truncated


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def rsi_wilder(close, n=14):
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    ru = up.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rd = dn.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rsi = 100.0 - 100.0 / (1.0 + ru / rd.replace(0.0, np.nan))
    rsi = rsi.where(rd != 0.0, 100.0)          # all-gain window
    rsi = rsi.where(~((rd == 0.0) & (ru == 0.0)), 50.0)  # flat window
    return rsi


def macd_hist(close, fast=12, slow=26, sig=9):
    macd = (close.ewm(span=fast, adjust=False).mean()
            - close.ewm(span=slow, adjust=False).mean())
    return macd - macd.ewm(span=sig, adjust=False).mean()


def compute_indicators(df, nsei_r252):
    """All columns are trailing-window values readable point-in-time at each row."""
    o = df.copy()
    c, h, l, v = o["Close"], o["High"], o["Low"], o["Volume"]
    o["sma50"] = c.rolling(50, min_periods=50).mean()
    o["sma150"] = c.rolling(150, min_periods=150).mean()
    o["sma200"] = c.rolling(200, min_periods=200).mean()
    o["sma200_prev21"] = o["sma200"].shift(21)
    o["lo252"] = l.rolling(252, min_periods=252).min()
    o["hi252"] = h.rolling(252, min_periods=252).max()
    o["r252"] = c / c.shift(252) - 1.0
    o["range15"] = h.rolling(15, min_periods=15).max() - l.rolling(15, min_periods=15).min()
    o["range30p"] = (h.rolling(30, min_periods=30).max()
                     - l.rolling(30, min_periods=30).min()).shift(15)
    o["pivot"] = h.rolling(15, min_periods=15).max()
    o["v10"] = v.rolling(10, min_periods=10).mean()
    o["v50"] = v.rolling(50, min_periods=50).mean()
    o["turn20"] = (c * v).rolling(20, min_periods=20).median()
    o["rsi14"] = rsi_wilder(c)
    o["hist"] = macd_hist(c)
    o["nsei_r252"] = nsei_r252.reindex(o.index, method="ffill")

    stage2 = ((c > o["sma50"]) & (o["sma50"] > o["sma150"]) & (o["sma150"] > o["sma200"])
              & (o["sma200"] > o["sma200_prev21"])
              & (c >= CFG["low52_mult"] * o["lo252"])
              & (c >= CFG["high52_mult"] * o["hi252"])
              & (o["r252"] > o["nsei_r252"]))
    contraction = ((o["range15"] / c < CFG["contraction_max"])
                   & (o["range15"] < o["range30p"]))
    dryup = o["v10"] < CFG["dryup_mult"] * o["v50"]
    liquid = o["turn20"] >= CFG["min_turnover"]
    o["signal_ok"] = (stage2 & contraction & dryup & liquid).fillna(False)
    return o


# ---------------------------------------------------------------------------
# Signal + entry generation (shared by all rule-sets)
# ---------------------------------------------------------------------------
def month_end_signal_dates(nsei_index):
    dates = []
    for p in pd.period_range(CFG["signal_month_start"], CFG["signal_month_end"], freq="M"):
        in_month = nsei_index[(nsei_index >= p.start_time) & (nsei_index <= p.end_time)]
        if len(in_month):
            dates.append(in_month[-1])
    return pd.DatetimeIndex(dates)


def generate_entries(universe, signal_dates):
    entries = []
    counts = dict(signals_raw=0, dedup_skipped=0, expired=0, entered=0)
    for sym, df in universe.items():
        idx_pos = {d: i for i, d in enumerate(df.index)}
        cand = [d for d in signal_dates if d in idx_pos and bool(df.at[d, "signal_ok"])]
        if not cand:
            continue
        hi = df["High"].values
        op = df["Open"].values
        block_until = -1
        for d in cand:
            counts["signals_raw"] += 1
            p = idx_pos[d]
            if p <= block_until:
                counts["dedup_skipped"] += 1
                continue
            pivot = float(df.at[d, "pivot"])
            trig = pivot * CFG["trigger_mult"]
            fill_base = pivot * CFG["fill_mult"]
            end = min(p + CFG["entry_window_td"], len(df) - 1)
            entry_pos = None
            for t in range(p + 1, end + 1):
                if hi[t] >= trig:
                    entry_pos = t
                    break
            if entry_pos is None:
                counts["expired"] += 1
                block_until = p + CFG["entry_window_td"]
            else:
                entry_px = max(float(op[entry_pos]), fill_base)
                entries.append(dict(symbol=sym, signal_date=d, pivot=pivot,
                                    entry_pos=entry_pos,
                                    entry_date=df.index[entry_pos],
                                    entry_px=entry_px))
                counts["entered"] += 1
                block_until = entry_pos + CFG["entry_window_td"]
    entries.sort(key=lambda e: (e["entry_date"], e["symbol"]))
    return entries, counts


# ---------------------------------------------------------------------------
# Exit simulation
# ---------------------------------------------------------------------------
def simulate_exit(df, entry_pos, entry_px, ruleset):
    """Walk forward from entry; return list of legs (pos, price, frac, reason)."""
    o = df["Open"].values
    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values
    rsi = df["rsi14"].values
    hist = df["hist"].values
    s50 = df["sma50"].values
    s200 = df["sma200"].values
    n = len(df)

    sl = entry_px * (1.0 - CFG["sl_pct"])
    t1 = entry_px * (1.0 + CFG["r_multiple_target"] * CFG["sl_pct"])  # 2R = +14%
    legs = []
    rem = 1.0

    # entry-day EOD stop check only (intraday extremes polluted by pre-entry trade)
    if c[entry_pos] < sl:
        return [(entry_pos, float(c[entry_pos]), 1.0, "sl_eod_entry_day")]

    trimmed = False       # B: RSI>80 half-trim done
    half_booked = False   # C: 2R half booked

    for t in range(entry_pos + 1, n):
        day_idx = t - entry_pos

        # 1) common hard stop — SL wins over any same-day target/trim
        if o[t] <= sl:
            legs.append((t, float(o[t]), rem, "sl_gap_open"))
            return legs
        if l[t] <= sl:
            legs.append((t, sl, rem, "sl"))
            return legs

        if ruleset == "A_jot":
            if h[t] >= t1:
                legs.append((t, t1, rem, "target_2R"))
                return legs
            if day_idx >= CFG["time_stop_a"]:
                legs.append((t, float(c[t]), rem, "time_stop_20td"))
                return legs

        elif ruleset == "B_wbonkers":
            if (not trimmed) and rsi[t] > 80.0:
                legs.append((t, float(c[t]), rem * 0.5, "trim_rsi80_half"))
                rem *= 0.5
                trimmed = True
            if (c[t] < s50[t]) and (c[t] < s200[t]) and (rsi[t] < 45.0) and (hist[t] < 0.0):
                legs.append((t, float(c[t]), rem, "trend_broken"))
                return legs

        elif ruleset == "C_hybrid":
            if (not half_booked) and h[t] >= t1:
                legs.append((t, t1, rem * 0.5, "target_2R_half"))
                rem *= 0.5
                half_booked = True
            if (c[t] < s50[t]) and (c[t] < s200[t]) and (rsi[t] < 45.0) and (hist[t] < 0.0):
                legs.append((t, float(c[t]), rem, "trend_broken"))
                return legs
            if day_idx >= CFG["time_stop_c"]:
                legs.append((t, float(c[t]), rem, "time_stop_30td"))
                return legs

    legs.append((n - 1, float(c[n - 1]), rem, "end_of_data"))
    return legs


def settle_trade(df, entry, legs):
    """Cash out a trade at Rs 10k notional with per-leg costs."""
    notional = CFG["notional"]
    cost = CFG["cost_per_leg"]
    shares = notional / entry["entry_px"]
    entry_cost = notional * cost
    proceeds = 0.0
    exit_cost = 0.0
    for (pos, px, frac, reason) in legs:
        val = frac * shares * px
        proceeds += val
        exit_cost += val * cost
    pnl = proceeds - notional - entry_cost - exit_cost
    last = legs[-1]
    return dict(
        symbol=entry["symbol"],
        signal_date=entry["signal_date"].strftime("%Y-%m-%d"),
        entry_date=entry["entry_date"].strftime("%Y-%m-%d"),
        entry_px=round(entry["entry_px"], 4),
        exit_date=df.index[last[0]].strftime("%Y-%m-%d"),
        hold_td=int(last[0] - entry["entry_pos"]),
        exit_reasons="+".join(l[3] for l in legs),
        final_reason=last[3],
        pnl_inr=pnl,
        ret_pct=pnl / notional * 100.0,
        r_mult=pnl / (notional * CFG["sl_pct"]),
        n_legs=len(legs),
        _legs=[(int(p), float(px), float(fr)) for (p, px, fr, _) in legs],
        _entry_pos=int(entry["entry_pos"]),
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def trade_metrics(trades):
    if not trades:
        return dict(n_trades=0)
    rets = np.array([t["ret_pct"] for t in trades])
    pnls = np.array([t["pnl_inr"] for t in trades])
    rs = np.array([t["r_mult"] for t in trades])
    holds = np.array([t["hold_td"] for t in trades])
    wins = pnls > 0
    gross_win = pnls[wins].sum()
    gross_loss = -pnls[~wins].sum()
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    avg_win = float(rets[wins].mean()) if wins.any() else 0.0
    avg_loss = float(-rets[~wins].mean()) if (~wins).any() else 0.0
    return dict(
        n_trades=int(len(trades)),
        win_rate_pct=round(float(wins.mean() * 100), 2),
        avg_R=round(float(rs.mean()), 3),
        expectancy_pct_per_trade=round(float(rets.mean()), 3),
        median_hold_td=float(np.median(holds)),
        profit_factor=(round(float(pf), 3) if math.isfinite(pf) else None),
        max_single_trade_loss_pct=round(float(rets.min()), 2),
        avg_win_pct=round(avg_win, 3),
        avg_loss_pct=round(avg_loss, 3),
        total_pnl_inr=round(float(pnls.sum()), 0),
    )


def book_curve(trades, universe, calendar):
    """Daily book P&L level (Rs) + concurrency, Rs 10k/trade, no compounding."""
    n = len(calendar)
    pnl = np.zeros(n)
    conc = np.zeros(n, dtype=int)
    if not trades:
        return pnl, 0
    cal_vals = calendar.values
    notional = CFG["notional"]
    cost = CFG["cost_per_leg"]
    for tr in trades:
        df = universe[tr["symbol"]]
        closes = df["Close"].reindex(calendar, method="ffill").values
        e = int(np.searchsorted(cal_vals, np.datetime64(pd.Timestamp(tr["entry_date"]))))
        legs = tr["_legs"]
        x = int(np.searchsorted(cal_vals,
                                np.datetime64(df.index[legs[-1][0]])))
        e = min(e, n - 1)
        x = min(x, n - 1)
        shares = notional / tr["entry_px"]
        seg_len = x - e + 1
        rem = np.ones(seg_len)
        realized = np.zeros(seg_len) - notional * cost  # entry cost from day 0
        for (pos, px, frac) in legs:
            li = int(np.searchsorted(cal_vals, np.datetime64(df.index[pos])))
            rel = max(0, min(li, x) - e)
            rem[rel:] -= frac
            realized[rel:] += frac * shares * px * (1.0 - cost) - frac * notional
        rem = np.clip(rem, 0.0, 1.0)
        seg_close = closes[e:x + 1]
        unreal = rem * (shares * seg_close - notional)
        seg_pnl = realized + unreal
        pnl[e:x + 1] += seg_pnl
        if x + 1 < n:
            pnl[x + 1:] += seg_pnl[-1]
        conc[e:x + 1] += 1
    return pnl, int(conc.max())


def book_metrics(pnl_level, base):
    eq = base + pnl_level
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    return dict(
        book_capital_inr=round(float(base), 0),
        book_total_return_pct=round(float(pnl_level[-1] / base * 100), 2),
        book_max_drawdown_pct=round(float(dd.max() * 100), 2),
    )


def exit_reason_counts(trades):
    out = {}
    for t in trades:
        out[t["final_reason"]] = out.get(t["final_reason"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# Evaluator integration
# ---------------------------------------------------------------------------
def run_evaluator(m, dd_pct, years, n_params):
    if not os.path.exists(EVALUATOR):
        return None
    cmd = [sys.executable, EVALUATOR,
           "--total-trades", str(m["n_trades"]),
           "--win-rate", str(m["win_rate_pct"]),
           "--avg-win-pct", str(max(m["avg_win_pct"], 0.0)),
           "--avg-loss-pct", str(max(m["avg_loss_pct"], 0.0)),
           "--max-drawdown-pct", str(dd_pct),
           "--years-tested", str(years),
           "--num-parameters", str(n_params),
           "--slippage-tested", "--output", "json"]
    try:
        # evaluator exits non-zero for non-DEPLOY verdicts — don't treat as error
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout)
        return dict(total_score=out["total_score"], percentage=out["percentage"],
                    verdict=out["verdict"], verdict_detail=out["verdict_detail"],
                    red_flags=[f["message"] for f in out.get("red_flags", [])])
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="smoke-test: only first N symbols alphabetically")
    ap.add_argument("--tag", default="", help="suffix for output files")
    ap.add_argument("--budget-min", type=float, default=20.0,
                    help="download runtime budget in minutes")
    ap.add_argument("--skip-eval", action="store_true")
    ap.add_argument("--universe", default=None,
                    help="constituents CSV with a 'Symbol' column "
                         "(default: auto-download the official Nifty 500 list)")
    args = ap.parse_args()
    tag = f"_{args.tag}" if args.tag else ""
    t_start = time.time()

    os.makedirs(BACKTEST_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    # ---- universe -----------------------------------------------------
    uni = pd.read_csv(resolve_universe(args.universe))
    symbols = sorted(str(s).strip() + ".NS" for s in uni["Symbol"].dropna().unique())
    if args.limit:
        symbols = symbols[:args.limit]
        log(f"SMOKE MODE: universe limited to first {args.limit} symbols")

    # ---- benchmark ----------------------------------------------------
    log("fetching ^NSEI benchmark...")
    nsei = None
    p = cache_path("^NSEI")
    if os.path.exists(p):
        nsei = pd.read_pickle(p)
    if nsei is None or len(nsei) == 0:
        nsei = clean_frame(yf.download("^NSEI", start=CFG["data_start"],
                                       end=CFG["data_end"], auto_adjust=True,
                                       progress=False))
        if nsei is None:
            sys.exit("FATAL: could not download ^NSEI")
        nsei.to_pickle(p)
    nsei_r252 = nsei["Close"] / nsei["Close"].shift(252) - 1.0
    nsei_sma200 = nsei["Close"].rolling(200, min_periods=200).mean()
    nsei_bull = (nsei["Close"] > nsei_sma200)
    log(f"  NSEI: {len(nsei)} rows {nsei.index[0].date()} .. {nsei.index[-1].date()}")

    # ---- stock data ----------------------------------------------------
    raw_data, dstats, truncated = fetch_universe(symbols, args.budget_min * 60)

    universe = {}
    insufficient = 0
    suspect = 0
    for s, df in raw_data.items():
        if df is None or len(df) < 300:
            insufficient += 1
            continue
        if df["Close"].pct_change().abs().max() > CFG["max_daily_move"]:
            suspect += 1
            continue
        universe[s] = df
    log(f"usable tickers: {len(universe)} (insufficient history: {insufficient}, "
        f"data-suspect excluded: {suspect}, failed downloads: {dstats['failed_download']})")

    # ---- indicators -----------------------------------------------------
    log("computing indicators...")
    t0 = time.time()
    for i, s in enumerate(list(universe)):
        universe[s] = compute_indicators(universe[s], nsei_r252)
        if (i + 1) % 100 == 0:
            log(f"  indicators {i+1}/{len(universe)}")
    log(f"  done in {time.time()-t0:.0f}s")

    # ---- signals + entries ----------------------------------------------
    signal_dates = month_end_signal_dates(nsei.index)
    log(f"signal dates: {len(signal_dates)} month-ends "
        f"({signal_dates[0].date()} .. {signal_dates[-1].date()})")
    entries, counts = generate_entries(universe, signal_dates)
    log(f"signals: {counts['signals_raw']} raw | dedup-skipped: {counts['dedup_skipped']} | "
        f"expired (no breakout in 20td): {counts['expired']} | ENTRIES: {counts['entered']}")

    # regime at entry
    for e in entries:
        b = nsei_bull.asof(e["entry_date"])
        e["regime"] = "bull" if bool(b) else "bear"

    # ---- simulate all rule-sets ------------------------------------------
    all_trades = {}
    for rs in RULESETS:
        trades = []
        for e in entries:
            df = universe[e["symbol"]]
            legs = simulate_exit(df, e["entry_pos"], e["entry_px"], rs)
            tr = settle_trade(df, e, legs)
            tr["regime"] = e["regime"]
            trades.append(tr)
        all_trades[rs] = trades
        log(f"simulated {rs}: {len(trades)} trades")

    # ---- book curves (common capital base) --------------------------------
    calendar = nsei.index
    curves, concs = {}, {}
    for rs in RULESETS:
        curves[rs], concs[rs] = book_curve(all_trades[rs], universe, calendar)
    base_all = CFG["notional"] * max(max(concs.values()), 1)
    log(f"max concurrent positions: {concs} -> common capital base Rs {base_all:,.0f}")

    # ---- assemble results ---------------------------------------------------
    years_tested = round((signal_dates[-1] - signal_dates[0]).days / 365.25, 2)
    n_params = {"A_jot": 3, "B_wbonkers": 6, "C_hybrid": 7}

    results = dict(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        config=CFG,
        run=dict(
            universe_csv=UNIVERSE_CSV,
            universe_size=dstats["universe_size"],
            truncated_to_250=truncated,
            cache_hits=dstats["cache_hits"],
            failed_download=dstats["failed_download"],
            insufficient_history=insufficient,
            data_suspect_excluded=suspect,
            usable_tickers=len(universe),
            signal_dates=len(signal_dates),
            signals_raw=counts["signals_raw"],
            dedup_skipped=counts["dedup_skipped"],
            expired_signals=counts["expired"],
            entries=counts["entered"],
            years_signal_span=years_tested,
            smoke_limit=args.limit,
            runtime_sec=None,  # filled at end
        ),
        rulesets={},
    )

    for rs in RULESETS:
        trades = all_trades[rs]
        m = trade_metrics(trades)
        bm = book_metrics(curves[rs], base_all) if trades else {}
        by_regime = {}
        for reg in ("bull", "bear"):
            sub = [t for t in trades if t["regime"] == reg]
            rm = trade_metrics(sub)
            if sub:
                sub_curve, sub_conc = book_curve(sub, universe, calendar)
                reg_base = CFG["notional"] * max(sub_conc, 1)
                rm.update(book_metrics(sub_curve, reg_base))
            by_regime[reg] = rm
        entry = dict(overall={**m, **bm},
                     by_regime=by_regime,
                     exit_reasons=exit_reason_counts(trades),
                     end_of_data_open=sum(1 for t in trades
                                          if t["final_reason"] == "end_of_data"))
        if not args.skip_eval and m.get("n_trades", 0) > 0:
            entry["evaluator"] = run_evaluator(
                m, entry["overall"].get("book_max_drawdown_pct", 0.0),
                years_tested, n_params[rs])
        results["rulesets"][rs] = entry

        # trades csv
        csv_path = os.path.join(BACKTEST_DIR, f"trades{tag}_{rs}.csv")
        pd.DataFrame([{k: v for k, v in t.items() if not k.startswith("_")}
                      for t in trades]).to_csv(csv_path, index=False)

    results["run"]["runtime_sec"] = round(time.time() - t_start, 1)

    out_path = os.path.join(BACKTEST_DIR, f"results{tag}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log(f"wrote {out_path}")

    # ---- console summary -----------------------------------------------------
    print("\n=== SUMMARY (after 0.3% round-trip costs) ===")
    hdr = f"{'metric':<28}" + "".join(f"{rs:>14}" for rs in RULESETS)
    print(hdr)
    keys = ["n_trades", "win_rate_pct", "avg_R", "expectancy_pct_per_trade",
            "median_hold_td", "profit_factor", "max_single_trade_loss_pct",
            "book_total_return_pct", "book_max_drawdown_pct"]
    for k in keys:
        row = f"{k:<28}"
        for rs in RULESETS:
            v = results["rulesets"][rs]["overall"].get(k)
            row += f"{v if v is not None else 'inf':>14}"
        print(row)
    for rs in RULESETS:
        ev = results["rulesets"][rs].get("evaluator")
        if ev and "verdict" in ev:
            print(f"{rs}: evaluator {ev['total_score']}/100 -> {ev['verdict']}")
    print(f"\ntotal runtime: {results['run']['runtime_sec']}s")


if __name__ == "__main__":
    main()
