# Onboarding — what the installer will ask you (human pre-read)

`prompt.md` is executed by your agent, not by you — but it's *about* you. Two minutes of prep makes the interview sharp. (Every question comes with an example answer, and the installer also sets up + authorizes any missing MCP — Groww's browser OAuth, Todoist's login — before the interview starts.)

## Before you start: drop your documents in
Copy into this folder (they stay local — everything personal is gitignored and never leaves your machine):
- **Salary slip / CTC PDF** — lets the plan factor taxes (e.g. India's New-Regime + employer-NPS lever) into its advice.
- **Portfolio export or notes** (`portfolio.md`, broker statements) — what you already hold, average prices.
- **Mutual-fund holdings — screenshot or statement.** ⚠️ The Groww MCP can only read your **stock** holdings; it cannot see your mutual funds. If you want funds tracked (a fund sleeve, SIPs, a keep-list), you *must* provide them — a screenshot of your MF screen, a statement PDF, or just type them during the interview (fund name, invested amount, current value). No upload = the plan manages stocks only.
- Anything else money-relevant (goals doc, EMI notes).

The agent converts each PDF to markdown under `personal/` using its own reading — no libraries, no upload to third parties beyond your chosen AI provider.

## The interview (what it asks, in order)
1. **"What's the W you're chasing?"** — your goal in 1–2 lines. *Better answers carry data:* "grow ₹50k to ~₹70k in 9 months, aggressive, can stomach a 30% drawdown" beats "make money". If you have numbers — corpus, horizon, target %, monthly top-ups — say them here.
2. **Corpus** — investable ₹ (or say `groww` and it reads your account).
3. **Horizon** — months (default 9).
4. **Targets** — stretch + realistic (or "you propose").
5. **Risk appetite** — conservative / moderate / aggressive.
6. **Guardrails** — default: no options, no forex, no index derivatives, no leverage. Keep or edit.
7. **Themes & universe** — sectors/stocks you want considered; anything you refuse to touch.
8. **Keep-list** — existing holdings that must never be rotated/sold.

## Then it works (you just approve)
- Reads your **Groww holdings + fundamentals**, runs the **VCP screen** over a universe seeded from your themes + holdings.
- Proposes: buckets (stocks / optional fund sleeve / optional event earmark / cash-dip buffer — summing exactly to your corpus), positions with 🟢 buy zone / 🔴 stop / 🎯 target / share counts, a watchlist.
- You iterate in plain language ("drop X", "smaller Y", "stop 320 on Z") until you approve.
- Then: `state.json` is built, views render, your Todoist project fills up, your command (`/w-bonkers` by default — you pick the name) is installed, scheduling is set. First review date lands as a ⏰ task.
- **It ends with a summary you can actually read:** your goal, your money split, every position as "buy X, exit below Y, book profit at Z", how you'll use it day to day, and what it will never do. Then one question — *"want to customize anything?"* — tweak whatever you like, or say **"all good"** and you're live.

## Privacy promises
- Personal docs, plan state, run archives: **local files in this folder**, all gitignored — `git push` physically can't include them.
- The only things that leave the machine: MCP calls to Groww/Todoist (your own accounts) and whatever your AI provider processes to run the agent.
- The agent never places orders — Groww's MCP is read-only for trading. Every trade is yours, at live prices you confirm.
