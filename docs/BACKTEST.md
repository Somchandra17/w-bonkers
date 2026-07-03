# Backtesting the rules — evidence for the STEP-4 exits

w-bonkers ships rules; this harness ships the receipts. `scripts/backtest_vcp.py` replays
point-in-time breakout entries over the Nifty 500 and compares exit rulesets on **identical
entries**, with Indian costs. It was built (July 2026) while consolidating w-bonkers with a
sibling system whose exits differed — the backtest was the referee.

**This is additive tooling: it changes nothing in the refresh flow, templates, or command.**

## Headline result

369 identical point-in-time entries (monthly signals, Jul 2023 – May 2026, 0.3% round-trip
costs, same-day SL-vs-target ambiguity resolved SL-first):

| Exit ruleset | Expectancy/trade | Profit factor | Win rate | Book return / max DD |
|---|---:|---:|---:|---:|
| A — hard SL + 2R profit cap + 20-day time stop | +0.03% | 1.008 | 43.9% | +0.1% / 3.6% |
| **B — w-bonkers STEP-4 style: SL + trend-broken exit + RSI>80 trim, no profit cap** | **+5.62%** | **2.19** | 33.1% | **+20.5% / 10.7%** |
| C — hybrid (SL + half at 2R + trailed trend exit + 30d stop) | +0.58% | 1.15 | 40.7% | +2.1% / 4.5% |

The w-bonkers-style exits win decisively. Profit caps and short time stops decapitate exactly
the winners that pay for all the losers (B's top trades ran +131% and +129%); C's trend-exit
never fired once because a 30-day time stop closes trades before a deep trend break can trigger.
Note the shape of B's edge: a ~33% win rate carried by large winners — losing streaks are normal
and by design.

## Market-regime finding (optional input for your pinned rules)

Splitting the same trades by where the index sat at entry:

| NSEI vs its 200-SMA at entry | n | Expectancy/trade | Profit factor |
|---|---:|---:|---:|
| Above | 341 | +6.13% | 2.28 |
| Below | 28 | −1.08% | 0.74 |

Entries taken below the index 200-SMA were net losers under every exit ruleset. If you want to
act on this, two additions that fit the `meta.pinned` philosophy (edit data, not the command) —
suggested only, not wired by this PR: a market-zone entry gate (full size above the 200-SMA,
reduced or none below) and a weekly loss budget (pause new entries once realized losses in a
rolling week exceed a set % of corpus).

## Run it

```bash
pip3 install yfinance pandas numpy
python3 scripts/backtest_vcp.py                 # auto-downloads the official Nifty 500 list
python3 scripts/backtest_vcp.py --limit 50      # quick smoke run
python3 scripts/backtest_vcp.py --universe my_universe.csv --tag custom
```

Outputs land in `backtest/` (gitignored): `RESULTS.md`, `results.json`, per-trade CSVs for
audit, and a price cache that makes re-runs take ~20 seconds.

## Honest caveats

- **Survivorship bias**: the universe is current index membership — fine for comparing rulesets
  against each other, not for absolute return claims.
- The entry screen is a simplified Minervini template (trend + contraction + volume dry-up +
  pivot break), not the full 5-component VCP scorer the skill uses.
- Monthly signal cadence under-samples fast regime transitions; EOD data only; the SL-first
  convention biases results conservative.
- The window is bull-heavy; the below-200-SMA sample is small (n=28).

Numbers above are from the 2026-07-03 run. Re-run for fresh data; your numbers will drift as
the window moves — that is the point.
