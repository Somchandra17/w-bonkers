# Talking to your plan — the Todoist feedback grammar

Your Todoist project is a two-way channel. The refresh command reads it **first**, before any market data. Two signals exist: **ticks** and **comments**.

## Ticks (completing a task)
- ✅ **Tick a BUY task only when the order actually FILLED on the exchange.** Not when you placed it. A resting limit order = task stays open. If you tick early, the next run checks your broker holdings, sees no fill, reopens the task, and tells you.
- Ticking a SELL/redeem/admin task when done = correct.
- The next run converts ticks into `status: "done"` in state.json — the plan then *owns* that leg (stops/targets tracked; it won't re-recommend buying).

## Comments (instructions)
Write a comment on any task — plain language, the agent parses intent:

| You write | The run does |
|---|---|
| `bought at 332` / `filled 12 @ 327.25` | marks done, records the fill price |
| `raise stop to 320` | updates that leg's stop in state.json |
| `skip` / `drop this` | removes/parks the leg (money returns to buffer) |
| `hold off till Monday` | keeps it pending, won't nag |
| `only 6 shares not 12` | resizes the leg + re-validates buckets |
| `why is the stop so tight?` | answers in the next run's report |

**Applied exactly once:** every processed comment's id is recorded (`meta.processed_comment_ids`), and the agent replies **`✓ applied: <what it did>`** under your comment. If there's no ✓ reply yet, it simply hasn't run since — it will.

## The ⏰ next-run task
Each run ends by (re)creating a dated **"⏰ [tag] Run /<command> next"** task — that's the plan telling you when it wants to be run (sooner in shaky regimes, later in calm ones). Comment on *that* task to talk to the next run without touching any position ("pause everything till I'm back from vacation" works).

## Orphaned tasks
Renamed or deleted a task by hand? The sync falls back to matching by the stable `[TAG] TICKER` title / ref, and re-links ids. Worst case it recreates the task — it will never duplicate a live one.
