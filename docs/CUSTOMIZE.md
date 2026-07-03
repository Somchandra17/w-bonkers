# Customize — make it yours (after install)

The system is built to be re-shaped by prompting your agent. The seams are deliberate.

## Change strategy inputs (no code, no command edits)
Everything the refresh command treats as FIXED lives in `state.json → meta.pinned`:
```json
"pinned": {
  "universe": "TICKER1,TICKER2,...",     // your scan list
  "broad_universe": "nifty200",          // full-mode wide screen
  "vcp_custom": "--trend-min-score 55 --min-contractions 2 --contraction-ratio 0.8",
  "vcp_broad":  "--trend-min-score 70 --min-contractions 2",
  "indicators": "RSI(14 Wilder), MACD(12,26,9), SMA 20/50/200, ATR(14), ...",
  "add_zone":   "Nifty 22,800-23,000",   // index zone where buffer deploys
  "min_switch_composite": 75,
  "anti_whipsaw_days": 10
}
```
Edit these (or tell your agent to), run `python3 scripts/render_plan.py --check`, done. **Never edit the installed command file to change strategy** — the command reads state at runtime, so your changes survive upgrades.

## Swap ANY service — the seams are deliberate
Every external service sits behind a narrow seam in the command file. Open your agent and ask; it rewires the seam and everything else keeps working.

**Task tool (Todoist → Linear/Notion/TickTick/a local file):** the sync payload (`todoist_tasks.json`) is deliberately tool-agnostic — `ref`, `title`, `due`, `description`. Tell your agent:
> "Replace the Todoist layer with **Linear** — update STEP 1 and STEP 6 of my `/<command>` file to read/write it, keep the exactly-once comment semantics and the tick-means-FILLED rule."
That's the whole seam: one read step, one write step, same payload.

**Data source (Groww MCP → your broker's MCP):** the market-data seam is STEP 3 of the command (prices, holdings, margins, movers) plus the STEP 0 preflight check. Tell your agent:
> "Swap the Groww MCP for **<your broker's MCP>** — map `get_ltp`/holdings/margins to its equivalents in STEP 0/1b/3, keep yfinance as the fallback and the read-only-for-trading rule."
Anything that exposes prices + your holdings works (Zerodha/Kite, Upstox, a custom MCP). Keep the guardrail: the agent must never gain order-placement powers.

**Scheduler:** cron, launchd, or any always-on agent runner — see SCHEDULING.md; the contract is one shell line.

## Different strategy than rotation?
v1's STEP-4 rules are **momentum/rotation-shaped** (EXIT&SWITCH on broken thesis, VCP-composite replacements, add-zone dips). They live as plain text in your installed command file — ask your agent to re-derive them for your style (e.g. "rewrite STEP 4 as a monthly SIP-plus-rebalance rule set; keep the propose-don't-auto-touch rule for held positions and the NO-CHANGE default"). Keep the invariants: state.json is truth, renderer is the only view-writer, default is NO CHANGE.

## Rename the command / move the folder
Re-run `prompt.md` and pick **reconfigure** — it regenerates the command file with the new name/path (state's `meta.command_name`/`meta.folder` update too) and removes the old one.

## Optional hosted board (Claude Code only)
`board.html` is the canonical view and works offline. If you want a private hosted copy on claude.ai, ask your agent to publish `_artifact-source.html` as an artifact once, then paste the URL into `meta.artifact_url` — every future run redeploys the SAME url.

## Upgrading w-bonkers
```bash
git pull
```
then open your agent and say *"re-run prompt.md in upgrade mode"* — it regenerates the command + docs from the new templates using your stored `install.json` answers, shows you the diff, and never touches `state.json` without asking. (Your data files are gitignored, so `git pull` can't conflict with them.)

## Publishing checklist (if you fork this repo)
Your data can't be committed *accidentally* (`.gitignore`), but before any `git push` run `git status --porcelain` and confirm it lists nothing personal — and never use `git add -f` in this folder.
