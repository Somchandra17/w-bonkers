# Scheduling — Todoist ⏰, cron, or both

Every run ends by writing `meta.next_review` (date + why) into state.json — the plan decides *when it wants to run next* (2–3 trading days in shaky regimes, ~5 neutral, ~10 calm; sooner if a position hugs its stop). Scheduling modes differ only in **who acts on that date**.

## Mode 1 — Todoist ⏰ task (default)
Each run (re)creates a dated **"⏰ [tag] Run /<command> next"** task. You open your agent in the plan folder and type the command. Zero infra, works everywhere, human stays in the loop. Best while you're learning the system.

## Mode 2 — cron (headless auto-runs)
Cron fires **daily**; the wrapper + the command's AUTO gate decide whether anything actually happens (today ≥ next_review, or unprocessed comments, or a stop breached → run; else exit silently). So a simple daily line gives you adaptive cadence:

```cron
# weekdays 16:05 IST — after close, when finals are out
5 16 * * 1-5  $HOME/stocks/scripts/run_refresh.sh claude quick
# optional monthly deep run — first Saturday 10:00
0 10 1-7 * 6  $HOME/stocks/scripts/run_refresh.sh claude full --force
# Codex flavor
5 16 * * 1-5  $HOME/stocks/scripts/run_refresh.sh codex quick
```
Install with `crontab -e` (the installer offers to do it for you, showing the exact line first).

**What the wrapper does** (`scripts/run_refresh.sh`): cds to the plan folder → gates on `next_review` → puts Node 22 first on PATH (Groww transport) → runs `claude -p "/<cmd> quick auto" --permission-mode acceptEdits` or `codex exec --cd <folder> --sandbox workspace-write ...` → logs to `runs/<date>/cron-<HHMM>.log`.

### Headless realities (read before trusting cron)
- **Groww auth ~7h, no refresh tokens.** A late-afternoon cron run often finds a dead token and *can't* open a browser. The command's AUTO mode degrades gracefully: prices fall back to yfinance last-close, the run completes, and it comments on your ⏰ task: *"Groww auth expired — open an interactive session to re-auth."* Cron works best on a machine where you use the Groww MCP interactively most days.
- **Nothing stalls waiting for you.** In AUTO mode every would-be question becomes a Todoist task/comment (`⚠️ [tag] needs your call: ...`) and the run exits without touching positions.
- **Permissions:** the installer writes a scoped `.claude/settings.json` allowlist (exact MCP + file + python tools) so headless runs don't hang on prompts. `--dangerously-skip-permissions` is **not** used by default — opt in only if you understand it.
- **macOS TCC:** cron can't read `~/Documents`/`~/Desktop`/`~/Downloads` without granting Full Disk Access. Easiest fix: keep the plan at `~/stocks`. Or use `launchd` (a LaunchAgent plist survives TCC better and reboots).
- **Always-on agent runners** (Agent-Hermes-style schedulers, a homelab box, a VPS with your CLIs installed): all of them work — the contract is just "execute the wrapper (or the same one-liner) on a schedule". The command is the brain; the runner is fungible.

## Mode 3 — both (recommended once you trust it)
Cron does the work; the ⏰ Todoist task remains your visible calendar (its description notes "cron armed — will auto-run on this date; comment here to talk to the next run"). If cron dies silently, the dated task still nudges you — a free dead-man switch.

Switch modes anytime: tell your agent *"switch my scheduling to cron/both/todoist"* — it updates `meta.schedule_mode` and the crontab.
