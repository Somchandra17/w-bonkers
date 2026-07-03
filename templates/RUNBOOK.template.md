# RUNBOOK — run this plan yourself (no internet, no agent needed)

_Last updated: {{INSTALL_DATE}} (Rev 1). If `state.json` disagrees with this file, `state.json` wins — this is the human manual, that is the machine truth. The refresh command re-syncs this file whenever the book changes._

## What this is
{{GOAL_TEXT}} — corpus **{{CORPUS_INR_PRETTY}}**, horizon ~{{HORIZON_MONTHS}} months, risk appetite {{RISK_APPETITE}}. Guardrails: **{{GUARDRAILS_TEXT}}**. Educational plan — every trade is placed by {{OWNER_NAME}}, at live prices.

## The book right now (Rev 1 · {{INSTALL_DATE}})
| Leg | Status | Qty | Entry / zone | 🔴 Stop | 🎯 Target | Note |
|---|---|---|---|---|---|---|
{{BOOK_TABLE_ROWS}}

**Money map:** {{MONEY_MAP_TEXT}}
**Keep-list (never rotated):** {{KEEP_LIST_TEXT}}

## Daily 5-minute manual check (broker app only)
1. **Stops:** any held stock CLOSED below its 🔴 stop? → sell it next morning, no debate.
2. **Targets:** any held stock in its 🎯 zone? → sell ~half, move stop to your entry price.
3. **Triggers:** any pending leg's condition met (pullback into zone / reclaim level / index dip)? → buy the planned qty, set the stop the same day.
4. **Resting orders:** re-place any lapsed day orders you still want.
5. **Add-zone:** index inside {{ADD_ZONE_TEXT}}? → deploy buffer in 2–3 slices into the strongest held names (above all MAs, RSI 50–65). Above the zone → do nothing.

## The decision rules (what the agent runs — identical by hand)
- **EXIT & SWITCH** a leg if: close < stop; OR news breaks the thesis (merger changing the story / big downgrade / regulator action / adverse event); OR trend broken = close < 50-DMA **and** < 200-DMA **and** RSI < 45 **and** MACD < 0. Replace with the strongest new setup in a theme you don't hold (screener composite ≥ 75).
- **TRIM** if target hit or RSI > 80 → sell ~half, stop to break-even.
- **ADD** small only if: held + above all 3 MAs + RSI 50–65 + index in the add-zone + buffer free.
- **Else HOLD.** Default is always NO CHANGE. Anti-whipsaw: never reverse a switch within 10 trading days unless its stop is hit.
- **Regime gate** (if enabled in your plan): the index closed below its own 200-day average → sell what the rules say to sell, but buy NOTHING new — replacement buys wait on the watchlist until the index reclaims the line. Exits are never gated.
- **Portfolio brakes** (if enabled): stop buying when the book's total open risk (sum of entry-minus-stop across positions) exceeds its cap, when this week's losses blow the weekly budget, or when the book falls the circuit-breaker % from its peak — in that last case, consciously decide what to trim. Selling is never automatic.
- **Tick a BUY task only when it FILLS**, not when you place the order.

## News check per holding (any browser, ~2 min each)
Search: `<name> merger OR acquisition OR stake` · `<name> downgrade OR target cut OR results` · `<name> SEBI OR corporate action OR block deal`. A hit that changes the story = treat as an EXIT signal; confirm the price reaction first.

## Monthly review
Trail stops up under each higher swing-low → book halves at targets → deploy buffer only in the add-zone → re-check breadth (% above 200-DMA) + FII/DII absorption; improving = lean in, narrowing = hold cash.

## Files & how to regenerate
`state.json` = single source of truth. Edit it, then `python3 scripts/render_plan.py` → regenerates `board.html` (opens offline in any browser), `tasks.md`, `tasks.ics`, `todoist_tasks.json`. Validate only: `--check`. History: `CHANGELOG.md`. Per-run market data: `runs/<date>/`. Rollbacks: `state.json.prev` / `.bak`.
