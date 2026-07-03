#!/usr/bin/env bash
# w-bonkers cron wrapper — safe to fire daily; the plan's own next_review decides which firings do work.
#
# Usage:  run_refresh.sh <claude|codex> <full|quick> [--force]
# Cron:   5 16 * * 1-5  /path/to/plan/scripts/run_refresh.sh claude quick
#
# Behavior:
#   1. cd to the plan folder (parent of this script's dir).
#   2. Gate: if today < state.json -> meta.next_review.date, exit 0 ("not due") unless --force.
#      (Unprocessed Todoist comments / stop breaches are re-checked by the command's own AUTO gate.)
#   3. Invoke the agent headlessly in AUTO mode, logging to runs/<date>/cron-<HHMM>.log.
set -euo pipefail

AGENT="${1:?usage: run_refresh.sh <claude|codex> <full|quick> [--force]}"
MODE="${2:?usage: run_refresh.sh <claude|codex> <full|quick> [--force]}"
FORCE="${3:-}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOLDER="$(dirname "$HERE")"
cd "$FOLDER"

# Node 22 first on PATH if present (the Groww MCP mcp-remote transport needs it; system Node 26 breaks it)
[ -d /opt/homebrew/opt/node@22/bin ] && export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
export TZ="${TZ:-Asia/Kolkata}"

# ---- gate on next_review ----
if [ "$FORCE" != "--force" ]; then
  GATE=$(python3 - <<'PY'
import json, datetime
try:
    nr = json.load(open("state.json"))["meta"].get("next_review") or {}
    d = nr.get("date")
    print("DUE" if (not d or datetime.date.today().isoformat() >= d) else "NOT_DUE")
except FileNotFoundError:
    print("NO_STATE")
except Exception as e:
    print("BAD_STATE")
PY
)
  case "$GATE" in
    NOT_DUE)  echo "$(date '+%F %T') not due yet (next_review in the future) — exiting."; exit 0 ;;
    NO_STATE) echo "$(date '+%F %T') state.json not found — is this a w-bonkers plan folder?"; exit 1 ;;
    BAD_STATE) echo "$(date '+%F %T') state.json unreadable — fix it before scheduling."; exit 1 ;;
  esac
fi

# ---- read command name from state ----
CMD=$(python3 -c "import json; print(json.load(open('state.json'))['meta'].get('command_name','w-bonkers'))")

# ---- log target ----
DAY=$(date +%F); HHMM=$(date +%H%M)
mkdir -p "runs/$DAY"
LOG="runs/$DAY/cron-$HHMM.log"

echo "$(date '+%F %T') w-bonkers cron: agent=$AGENT mode=$MODE cmd=/$CMD folder=$FOLDER" | tee -a "$LOG"

case "$AGENT" in
  claude)
    # Relies on the project .claude/settings.json allowlist written at install time.
    # --dangerously-skip-permissions is deliberately NOT used here; see docs/SCHEDULING.md to opt in.
    claude -p "/$CMD $MODE auto" --permission-mode acceptEdits >>"$LOG" 2>&1
    ;;
  codex)
    codex exec --cd "$FOLDER" --sandbox workspace-write \
      "Run the $CMD refresh now, mode: $MODE auto, exactly per its skill/AGENTS.md spec." >>"$LOG" 2>&1
    ;;
  *)
    echo "unknown agent '$AGENT' (use claude|codex)" | tee -a "$LOG"; exit 1 ;;
esac

echo "$(date '+%F %T') done (exit $?)" | tee -a "$LOG"
