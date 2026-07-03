# /{{COMMAND_NAME}} — deterministic, feedback-driven plan refresh (w-bonkers)

You **update `state.json`** (the single source of truth) in `{{FOLDER_PATH}}`; `scripts/render_plan.py` regenerates every view deterministically. Default action is **NO CHANGE** — only act when the user's Todoist feedback (STEP 1) or a STEP-4 rule fires on fresh data. Same state, same pinned inputs, same files every run → results are reproducible, never re-rolled.

**Arg:** `full` (default — pinned-universe screen + broad-market screen + regime deep-dive) or `quick` (holdings health + per-holding news + prices/levels only; skip the broad screen and deep regime work). An additional `auto` arg marks a headless/cron run — see AUTO MODE at the bottom.

All personalization lives in `state.json → meta` (owner, tag, todoist_project, corpus, guardrails, `pinned.*` inputs). **Read them from state — never hardcode.**

## STEP 0 — Preflight (top-to-bottom; PAUSE and ask if a REQUIRED item is missing; never fake data)
Report a ✅/❌ checklist:
1. **[REQUIRED] Groww MCP** (`mcp__growwmcp__*` tools) → if ❌ ask: *"Groww MCP not found — run from a local agent session in {{FOLDER_PATH}}. Stop, or proceed with last-close data only via yfinance? (stop / last-close)"*.
2. **[REQUIRED] Skills**: `nse-vcp-screener`, `technical-analyst`, `india-news-tracker`, `fii-dii-flow-tracker`, `india-market-breadth`, `scenario-analyzer` → for any missing ask *"install from github.com/ajeeshworkspace/indian-trading-skills, or proceed without? (install / proceed)"*.
3. **[REQUIRED] Files**: `{{FOLDER_PATH}}/state.json` + `{{FOLDER_PATH}}/scripts/render_plan.py` present? If ❌ ask (the folder may have moved — see docs/CUSTOMIZE.md).
4. **[REQUIRED] Todoist MCP** (`mcp__*todoist*` tools; search "todoist" if deferred) → if ❌ ask *"restart the session so the MCP loads, or skip task-sync this once? (restart / skip)"*.
5. **[TIMING]** `resolve_market_time_and_calendar` → if pre-open / market closed, note: *"prices will be last-close; a price refresh alone won't move levels — news/structure still checked."*
6. [OPTIONAL] yfinance — fallback price source only (Groww is primary).
7. **[STATE]** run `python3 scripts/render_plan.py --check` from `{{FOLDER_PATH}}`. If it prints `ERROR`, stop and fix `state.json` before anything else.

## STEP 1 — START HERE: read the user's feedback, then reconcile (before any market work)
Snapshot the last-good state first: `cp state.json state.json.prev` (rollback point).
**1a. Read the Todoist project named in `meta.todoist_project` — every task's status + every comment.**
   - **Act ONLY on comments whose id is NOT in `meta.processed_comment_ids`** — each comment is applied exactly once, never re-processed. A comment is a direct instruction → act on it FIRST (highest priority) and write the intent into `state.json`. Examples: *"bought at 332"* → set that position `status:"done"` + record the fill; *"raise stop to 320"* → update `stop`; *"skip"/"drop"* → remove or park; *"hold off"* → keep `pending`; *a question* → answer it in STEP 7.
   - **After acting on a comment: post a Todoist reply `✓ applied: <what you did>` and append the comment id to `meta.processed_comment_ids`.**
   - **Completed task** → that position `status:"done"` (the user owns it — don't re-recommend buying). A BUY task ticked while its order hasn't actually filled → reopen it and tell the user (tick = FILLED, not placed). **Pending** → carry forward.
**1b. Reconcile:** `state.json` (canonical) + `CHANGELOG.md` (history) + live `get_equity_portfolio_holdings`. Sort every leg into **DONE / PENDING / UNPLANNED**. Mutual-fund "keep" items don't appear in equity holdings — track separately. **First run ever** (empty history, no fills): everything is PENDING — that's normal, proceed.
**1c.** Preserve the plan unless a comment (1a) or a STEP-4 rule fires. `meta.goal` is the standing objective.

## STEP 2 — Pinned inputs (identical every run — read from state, do not vary)
- Corpus `meta.corpus_inr`; guardrails `meta.guardrails`; spread 8–10 names + buffer.
- **Universe (FIXED):** `meta.pinned.universe` + all current holdings. Broad screen (full mode only): `meta.pinned.broad_universe`.
- **VCP params (FIXED):** custom → `meta.pinned.vcp_custom`; broad → `meta.pinned.vcp_broad`.
- **Indicators (FIXED):** `meta.pinned.indicators`.

## STEP 3 — Fresh data (Groww is PRIMARY; post-close preferred)
- **Prices from Groww first:** `get_ltp` (+ `fetch_historical_candle_data` / `get_historical_technical_indicators` as needed) for every holding + universe name, plus the index & VIX. **yfinance = fallback only**; validate symbols, skip delisted/renamed.
- Also: `get_available_margin_details`, `get_my_trading_positions_today`, `fetch_ipo_listings` (if an `ipo` block exists), `fetch_market_movers_and_trending_stocks_funds([HIGH_MOMENTUM, YEARLY_HIGH, STOCKS_IN_NEWS])`.
- **Skills:** `nse-vcp-screener` on `pinned.universe` (always) and `pinned.broad_universe` (full mode); `technical-analyst` indicators for every holding + top screener hits; `india-news-tracker` with **deterministic per-holding queries** — for each ticker: `"<name> merger OR acquisition OR stake"`, `"<name> downgrade OR target cut OR results"`, `"<name> SEBI OR corporate action OR block deal"`; `fii-dii-flow-tracker` + `india-market-breadth` + `scenario-analyzer` (**pin scenarios to `meta.horizon_months`**).

## STEP 4 — Deterministic rules (default = HOLD / keep pending)
Comments from 1a are already applied and win. Then per position:
- **EXIT & SWITCH** if: last close < `stop`; OR targeted news flags a broken thesis (merger / downgrade / SEBI action / adverse event); OR trend broken (close < 50-DMA **and** < 200-DMA, RSI < 45, MACD < 0). **HELD (done) positions → do NOT auto-change; PROPOSE in STEP 7 and ask. PENDING → apply to state.json.** Replacement = deterministic: highest VCP composite in an un-held theme, **min composite ≥ `pinned.min_switch_composite`**, tie-break RS → liquidity; give buy zone / stop / target. **Anti-whipsaw:** never reverse a switch, or re-switch a name whose `switched_on` is within the last `pinned.anti_whipsaw_days` trading days, unless its stop is hit; stamp `switched_on` on any new switch.
- **TRIM** if target hit or RSI > 80 (held only) → propose. **ADD** (small) if HOLD + above all MAs + RSI 50–65 + index inside `pinned.add_zone` + buffer free.
- else **HOLD** (levels re-anchored to fresh RSI/MA/ATR). New names only via EXIT&SWITCH or composite ≥ +10 vs the weakest holding. **If nothing fires: "No changes — prices/levels/dates refreshed only."**

## STEP 5 — Persist + render + archive (state.json = truth; render_plan.py = the only view-writer)
1. **Edit `state.json`**: positions (status, fresh entry/stop/target), buckets; set `last_refreshed` + `prices_asof` + `run_mode`. **Set `meta.next_review` {date, reason} from the market trend**: cautious/volatile regime OR a known event within ~5 sessions → 2–3 trading days (or the session before the event); neutral → ~5; calm strong-trend → ~10; never past the next central-bank decision / earnings cluster / subscribed-event open; pull it SOONER if any position sits near its stop or a trigger looks imminent.
2. **Run `python3 scripts/render_plan.py`** — validates, backs up state → `.bak`, regenerates `board.html`, `_artifact-source.html`, `tasks.md`, `tasks.ics`, `todoist_tasks.json`. **If it prints `ERROR`, fix state.json and re-run — never publish a failed render.** Do NOT hand-edit the HTML.
3. **If `meta.artifact_url` is non-null** (Claude Code only): redeploy the SAME artifact from `_artifact-source.html` to that URL. If null, `board.html` is the canonical view — skip this.
4. **Only if something changed** (a comment action, switch, trim, add, or a level move beyond rounding): bump `meta.rev` and append a dated `CHANGELOG.md` entry. **True no-op:** don't bump rev — update only `last_refreshed`/`prices_asof` and report "no change".
5. **Archive the run — the folder must stay self-contained (offline- and other-agent-usable):** append to `runs/<YYYY-MM-DD>/run-summary.md`: run time + mode + LIVE/LAST-CLOSE, prices captured (incl. index/VIX), FII/DII + breadth + scenario numbers, news-delta one-liners per holding, screener top hits, per-position STEP-4 verdicts, feedback applied, actions taken. Copy raw screener outputs into `runs/<date>/screens-<HHMM>/`. If your platform keeps persistent memory notes about this plan, mirror them into `context/`. If the book or structure changed, refresh `RUNBOOK.md` (its "book right now" table must match state.json) and `MANIFEST.json`. **Ad-hoc data fetches outside a full run also get saved** to `runs/<date>/adhoc-<topic>.md` — analysis data must never live only in the conversation.

## STEP 6 — Todoist sync (upsert into `meta.todoist_project` — never duplicate)
- Read `todoist_tasks.json` (deterministic payload: each entry has `ref`, `title` `[<meta.tag>] ...`, `due`, and a description with 🟢 Buy zone / 🔴 Stop-loss / 🎯 Sell-target / qty / when / why).
- Ensure the project exists. Per entry: **match by the position's stored `todoist_task_id`** (preferred) **else by the `[<tag>] <ticker>` title / `ref`** → **update** if present, else **create** and write the new id into `state.json` (`positions[].todoist_task_id`). **Do NOT re-render or re-deploy after writing ids** (they're not shown on the board) — avoids a render→sync→render loop.
- **Complete** tasks whose position is `done` (fill verified); add new SWITCH tasks; remove cancelled. Tick = FILLED only.

## STEP 7 — Report (fixed format)
1) Preflight result; 2) LIVE or LAST-CLOSE; 3) **Todoist feedback acted on** (each → what you did); 4) regime one-liner; 5) **WHAT CHANGED** (or "no change"); 6) **EXIT/SWITCH proposals awaiting confirmation** (held positions); 7) **today's actions** with 🟢 buy / 🔴 stop / 🎯 sell; 8) Todoist sync result; 9) **Next recommended run** (`meta.next_review` date + why) — also upserted as the dated **"⏰ [<tag>] Run /{{COMMAND_NAME}} next"** Todoist task.

## AUTO MODE (cron / headless runs — arg `auto`)
- **Gate first:** if today < `meta.next_review.date` AND there are no unprocessed Todoist comments and no position closed beyond its stop → write one line to `runs/<date>/cron-skip.log` and exit cleanly. Cron may fire daily; this gate keeps the effective cadence adaptive.
- **Never stall on a human:** every "PAUSE and ask" becomes **ask via Todoist** — create/comment a task titled `⚠️ [<tag>] needs your call: <question>` and exit cleanly without mutating positions. This applies to EXIT&SWITCH proposals on held positions too.
- **Groww auth dead** (typical after ~7h; browser re-auth impossible headlessly): fall back to yfinance LAST-CLOSE for prices, set `prices_asof` accordingly, complete the run, and comment on the ⏰ task: *"Groww auth expired — open an interactive session to re-auth."* If Todoist itself is unreachable, log to `runs/<date>/cron-error.log` and exit non-zero.

Never invent prices. Educational analysis, not investment/tax advice — the user places every trade and confirms live prices before every buy.
