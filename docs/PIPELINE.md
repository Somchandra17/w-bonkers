# The pipeline — architecture contract

Read this to understand *why* w-bonkers behaves the way it does. These are laws, not suggestions; every component depends on them.

## The two invariants
1. **`state.json` is the single source of truth.** Positions, levels, buckets, regime, pinned inputs, the next-review date — everything lives there. Rendered views, Todoist tasks, calendars are *projections* of it. If a view disagrees with state, the view is wrong.
2. **`scripts/render_plan.py` is the only view-writer.** Same state.json → byte-identical output, every run, forever. The agent edits *data*; a deterministic script produces *views*. This kills LLM drift: two runs on the same day produce the same board, not two creative rewrites.

## The refresh loop (STEP 0–7)
```
STEP 0  Preflight        — MCPs, skills, files, market clock. Missing REQUIRED item → ask, never fake.
STEP 1  Feedback FIRST   — read the Todoist project: ticks + comments. Each comment is an instruction,
                           applied exactly once (ids recorded in meta.processed_comment_ids), replied to
                           with "✓ applied: ...". Completed BUY = FILLED (a placed-but-unfilled order is
                           reopened). Then reconcile state vs live broker holdings.
STEP 2  Pinned inputs    — corpus, universe, screen params, indicators: read from meta.pinned. Identical
                           every run. Changing strategy = edit state, never the command.
STEP 3  Fresh data       — broker MCP primary (prices, holdings, margins, movers), yfinance fallback;
                           VCP screens; deterministic per-holding news queries; flows/breadth/scenarios.
STEP 4  Rules            — DEFAULT = NO CHANGE. EXIT&SWITCH only on: stop breached / thesis-breaking news /
                           trend broken. TRIM on target or RSI>80. ADD only inside the add-zone. Held
                           positions are never auto-changed — proposals only. Anti-whipsaw: a switch can't
                           be reversed for N trading days unless stopped out.
STEP 5  Persist + render — edit state.json; bump rev ONLY on real change; run render_plan.py (validates:
                           buckets == corpus, stop < entry < target); archive EVERYTHING fetched into
                           runs/<date>/ (the folder must stay usable offline and by other agents).
STEP 6  Task sync        — upsert todoist_tasks.json into the project by stable ref/id. Never duplicate.
                           Complete tasks only when the position is done (filled).
STEP 7  Report           — fixed format, ending with the next recommended run date (meta.next_review),
                           which becomes a dated ⏰ Todoist task (and the cron gate).
```

## Rev & changelog discipline
`meta.rev` bumps **only** when something actually changed (a feedback action, switch, trim, add, fill, or a level move beyond rounding) — and every bump gets a dated `CHANGELOG.md` entry saying *what and why*. A pure price refresh is a no-op: timestamps update, rev doesn't. This keeps the history meaningful.

## The archive guarantee
Every run writes `runs/<date>/run-summary.md` (prices, flows, breadth, news findings, screen results, verdicts, actions) plus raw screener output. Ad-hoc fetches get saved too (`runs/<date>/adhoc-*.md`). Combined with `RUNBOOK.md` (the offline manual) and `MANIFEST.json` (the machine index), the folder is fully usable with **no internet, no agent, no cloud** — and any other AI agent pointed at `MANIFEST.json` can take over cold.

## Safety posture
- The agent **never places orders**. Broker MCPs used here are read-only for trading; the human places every trade and confirms live prices.
- User data (state, personal docs, runs, changelog) is gitignored — a fork/push can't leak it.
- Educational tooling, not investment advice.
