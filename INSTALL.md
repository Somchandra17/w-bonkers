# INSTALL.md — w-bonkers installer (executed by YOUR AI agent)

> **Human:** open Claude Code or Codex in this folder and say: **"Read INSTALL.md and execute it."** Then just answer its questions. Prep tips: [docs/ONBOARDING.md](docs/ONBOARDING.md).

---

**Agent: you are the w-bonkers installer.** Execute the phases below in order, in this folder. Ground rules:
- **Ask, don't fake.** If a REQUIRED check fails, stop and help the human fix it (guides in `docs/`). Never simulate data, never skip a gate, never pretend a tool is connected.
- **Read before write; confirm before overwrite.** Record progress in `install.json` after every phase so a crashed install resumes cleanly.
- **Never commit or push anything.** User data is gitignored by design; do not fight that.
- Educational tooling: the human places every trade. Never claim you can place orders.

## Phase 0 — Detect & idempotency
1. Detect: platform (Claude Code / Codex / other), absolute path of this folder (→ `FOLDER_PATH`), `python3 --version`, today's date + IST time.
2. **If `install.json` already exists**, this system was installed before. Ask exactly:
   *"w-bonkers is already installed here (on {date}). What do you want? **repair** (re-verify everything, fix broken pieces) / **reconfigure** (change specific answers — command name, scheduling, etc. — and regenerate affected files) / **upgrade** (regenerate command + docs from the current templates, keeping all your answers and state.json) / **fresh** (start over — I'll archive your current state.json to runs/uninstall-{date}/ first)"*
   Execute only what they pick. **Never re-interview or overwrite `state.json` blindly.** Otherwise continue.

## Phase 1 — Tooling gate (hard requirements; before any portfolio work)
Print a live ✅/❌ checklist and resolve every ❌ before moving on (each: fix → retry → or abort with a clear summary):
1. **Groww MCP** — are `mcp__growwmcp__*` tools available? Verify with a REAL call (`get_equity_portfolio_holdings`). Missing/broken → walk through [docs/PREREQUISITES.md §2](docs/PREREQUISITES.md) (the Node-22 + `mcp-remote` + port-52155 wrapper), have the human complete the browser OAuth, re-verify.
2. **Todoist MCP** — REQUIRED. Missing → say: *"Todoist is required for the feedback loop (you can swap it for another tool later — see docs/CUSTOMIZE.md). Set it up now? (guide me / abort)"* and guide per PREREQUISITES §3. A session restart is usually needed after registering an MCP — tell them, then resume at this phase (install.json remembers).
3. **Skills** — check `~/.claude/skills/` for: `nse-vcp-screener`, `technical-analyst`, `india-news-tracker`, `fii-dii-flow-tracker`, `india-market-breadth`, `scenario-analyzer`. For any missing: `git clone https://github.com/ajeeshworkspace/indian-trading-skills` to a temp dir and copy the missing skill folders in. Re-verify all six.
4. **python3 + deps** — `python3 -c "import yfinance"`; missing → `pip3 install yfinance pandas niftystocks` (offer `--user`/venv on PEP-668 systems).
5. **Renderer sanity** — `python3 scripts/render_plan.py --check` should fail with "state.json not found" (expected pre-state; proves python + script work).

## Phase 2 — Personal documents
Ask: *"Drop any personal finance docs into this folder now — salary/CTC PDF, broker statements, a portfolio.md, notes. Everything stays local and gitignored. Tell me when done (or say 'none')."*
For each PDF found: read it with your own document reading (no pdf libraries), write a faithful markdown conversion to `personal/<slug>.md` (frontmatter: source filename + conversion date), move the original into `personal/`, and summarize what you extracted in 2–3 lines for confirmation. Salary docs: extract CTC structure, tax regime, deductions — this feeds the optional `tax` block later.

**Mutual funds (explicit step — do not skip):** the Groww MCP exposes **stock holdings only** — it cannot read the user's mutual-fund portfolio. Say so, then ask: *"If you want mutual funds tracked in this plan (a fund sleeve, SIPs, or a keep-list), upload a screenshot or statement of your MF holdings — or just type them: fund name, invested amount / units, current value. Groww's MCP can't see them, so this is the only way. (or say 'no funds')."* Read whatever they provide (screenshots via your vision) and write `personal/mutual-funds.md`. This file becomes the source for state.json's `fund` block and `keep_not_rotated` — and every future refresh tracks MF legs from the user's ticks/comments only, never from broker data.

## Phase 3 — Goal interview
Ask in order (accept free text; push gently for numbers):
1. *"What's the W you're chasing? One or two lines — with numbers if you have them (corpus, target %, timeframe)."*
2. *"Investable corpus in ₹?"* (or `groww` → read total account value and confirm)
3. *"Horizon in months? (default 9)"*
4. *"Target return — stretch and realistic? (or say 'you propose')"*
5. *"Risk appetite: conservative / moderate / aggressive?"*
6. *"Guardrails — default: no options, no forex, no index derivatives, no leverage. Keep or edit?"*
7. *"Themes or stocks you want in the scan universe? Anything you refuse to touch?"*
8. *"Existing holdings to KEEP forever (never rotated or sold by this plan)?"*
Record all answers in `install.json`.

## Phase 4 — Portfolio analysis → plan proposal
1. Pull live holdings + margins (Groww — **stocks only**; merge the mutual-fund picture from `personal/mutual-funds.md` for the full portfolio), fundamentals for held names, index level + VIX.
2. Build the proposed **universe**: user themes + current holdings + liquid leaders in those themes (~30–40 NSE names). Run the `nse-vcp-screener` skill over it (params: `--trend-min-score 55 --min-contractions 2 --contraction-ratio 0.8`) and `technical-analyst` indicators on candidates.
3. Derive the opening book sized to risk appetite: **buckets** (e.g. stocks / optional fund sleeve / optional event earmark / cash-dip buffer) **summing exactly to the corpus**, positions with 🟢 entry zone / 🔴 stop / 🎯 target / share counts / one-line reasons, an add-zone (~5–7% below the current index, confirmable), a watchlist. Market closed → anchor to last close and say so.
4. Present it as a table + bucket math. Ask: *"Reply **approve**, or tell me changes ('drop X', 'smaller Y', 'stop 320 on Z')."* Iterate until approved.

## Phase 5 — Materialize state
1. Fill `templates/state.template.json` → `./state.json` (delete the `_comment*` keys): meta (owner, plan_label, tag — ask for a short tag, default `W`; goal, corpus, horizon, risk, guardrails, folder, schedule_mode placeholder, next_review = first review date you propose), regime (today's read), buckets, positions, watchlist, keep-list; `tax` block only if Phase 2 produced one; `fund`/`ipo` only if the plan includes them.
2. `python3 scripts/render_plan.py --check` → fix until **0 errors**.
3. Fill `templates/RUNBOOK.template.md` → `./RUNBOOK.md`, `templates/MANIFEST.template.json` → `./MANIFEST.json`, `templates/CHANGELOG.seed.md` → `./CHANGELOG.md`. Create `runs/`, `context/`, `personal/` dirs. Write `install.json` (all answers + template version + date).

## Phase 6 — Install the command
1. Ask: *"Name your refresh command — you'll type this daily. Default: **w-bonkers** (→ `/w-bonkers`). Lowercase-kebab only."* Validate; check collisions in `~/.claude/commands/` and `~/.claude/skills/` (offer rename/overwrite).
2. Ask: *"Todoist project name for this plan? Default: '{plan_label}'."* Check for an existing project with that name — if one exists, ask reuse vs a new name (avoid collisions on shared accounts).
3. Ask: *"Install the command for: Claude Code / Codex / both?"*
4. Generate from `templates/command.template.md` (substitute `{{COMMAND_NAME}}`, `{{FOLDER_PATH}}`), write `meta.command_name` + `meta.todoist_project` + `meta.tag` into state.json, then install:
   - **Claude Code** → `~/.claude/commands/<name>.md`
   - **Codex** → `~/.claude/skills/<name>/SKILL.md` with name/description frontmatter if `~/.codex/skills` symlinks to `~/.claude/skills` (common); else `~/.codex/skills/<name>/SKILL.md` directly; no skills support → append the full command body under the marker line in this folder's `AGENTS.md`.
   - Keep a reference copy at `context/command-installed.md`.

## Phase 7 — Scheduling
Ask: *"How should runs be scheduled? **1** Todoist ⏰ task only (default — the plan picks its own next date, you run it) / **2** cron (headless auto-runs — read the caveats) / **3** both."* Set `meta.schedule_mode`.
If cron (2/3): summarize the caveats from [docs/SCHEDULING.md](docs/SCHEDULING.md) (Groww ~7h token → degraded runs; macOS TCC → prefer `~/stocks`-style paths); ask for a time (default weekdays 16:05 IST); **show the exact crontab line and get an explicit yes** before `(crontab -l; echo "<line>") | crontab -`. For Claude Code also write a scoped `.claude/settings.json` permissions allowlist (the exact `mcp__growwmcp__*`, `mcp__todoist__*`, Bash(python3 …), Read/Edit/Write patterns used by the command) so headless runs don't stall — never write `--dangerously-skip-permissions` anywhere.

## Phase 8 — First render + Todoist bootstrap
1. `python3 scripts/render_plan.py` (full render — board.html, tasks.md, tasks.ics, todoist_tasks.json).
2. Create the Todoist project; upsert every entry from `todoist_tasks.json` (titles `[<tag>] ...`, descriptions with 🟢/🔴/🎯); write returned task ids into `state.json → positions[].todoist_task_id`. **Do not re-render after backfilling ids.**
3. Create the dated **"⏰ [<tag>] Run /<command> next"** task for the first review date.

## Phase 9 — Verification + handoff (prove it, don't declare it)
Run and show each check:
- [ ] `python3 scripts/render_plan.py --check` → 0 errors
- [ ] `board.html` exists — print its absolute path (open it in a browser: works offline)
- [ ] buckets sum == corpus (print the math)
- [ ] Todoist: project exists, N tasks + 1 ⏰ task, ids backfilled in state.json
- [ ] command file exists on the chosen platform(s) — print path(s)
- [ ] skills 6/6 present; Groww + Todoist MCPs respond
- [ ] **`git status --porcelain` lists NO user files** (state.json, personal/, runs/, RUNBOOK, MANIFEST, CHANGELOG, install.json all ignored — print proof)
- [ ] if cron: `crontab -l` shows the line; `scripts/run_refresh.sh <agent> quick` dry-runs to "not due yet"
Then hand off, verbatim-ish:
> **"You're live at Rev 1.** 📌 Tick a BUY task only when it FILLS — not when you place the order. 💬 Comment on any task to instruct the next run ('bought at 332', 'raise stop to 320', 'skip'). ⏰ First review: {date} — or just run `/{command}` anytime. Your board: {folder}/board.html. Take the W."
