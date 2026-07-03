# Prerequisites

Everything the installer (INSTALL.md) checks for — set these up before or during install. The installer walks you through any missing piece; nothing is faked.

## 1. An agentic CLI (pick one or both)
| | Claude Code | Codex CLI |
|---|---|---|
| Install | https://claude.com/claude-code | `brew install codex` / OpenAI docs |
| Command lands in | `~/.claude/commands/<name>.md` | `~/.codex/skills/<name>/SKILL.md` (or symlinked `~/.claude/skills/`), fallback: this folder's `AGENTS.md` |
| MCP registration | `claude mcp add <name> -- <cmd>` | `~/.codex/config.toml` `[mcp_servers]` |

## 2. Groww MCP (primary market-data source — REQUIRED)
Groww's MCP (`https://mcp.groww.in/mcp`) gives live prices, holdings, margins, movers, IPOs. Two known gotchas, both solved by a tiny wrapper:

1. **Must connect via `mcp-remote` with fixed OAuth callback port `52155`.** Groww's OAuth app does exact-match redirect validation and only whitelists `localhost:52155` (and requires a confidential client) — so a native `type: http` connector with a random port fails at `/authorize` with `400 Invalid redirect URL`.
2. **Node 23+ can break mcp-remote's transport** (observed on Node 26: `initialize` is sent, the reply is never processed → "Failed to connect"). Fix: run it under **Node 22**.

**The wrapper** — save as `~/.local/bin/groww-mcp.sh`, `chmod +x` it:
```bash
#!/usr/bin/env bash
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"   # brew install node@22 (keg-only is fine)
exec npx mcp-remote https://mcp.groww.in/mcp 52155
```
Register it:
```bash
# Claude Code
claude mcp add growwmcp -- ~/.local/bin/groww-mcp.sh
# Codex — ~/.codex/config.toml
[mcp_servers.growwmcp]
command = "/Users/YOU/.local/bin/groww-mcp.sh"
```
First connect opens a browser OAuth (click Allow). **Groww issues no refresh tokens — sessions last ~7 hours**; when expired, mcp-remote re-opens the browser on next use. Tokens cache in `~/.mcp-auth/`. This matters for cron mode — see [SCHEDULING.md](SCHEDULING.md).

**Scope note — stocks only:** the Groww MCP reads your *equity* holdings, prices, margins and movers; it does **not** expose your mutual-fund portfolio (it can only look up public fund details/NAVs). If you want MFs in your plan, the installer explicitly asks you to provide them (screenshot / statement / typed) — and refresh runs track those legs from your Todoist ticks & comments, never from broker data.

## 3. Todoist MCP (the feedback loop — REQUIRED)
The plan talks to you through a Todoist project: tasks carry 🟢 buy / 🔴 stop / 🎯 target; **your ticks and comments are the input for the next run** ([FEEDBACK.md](FEEDBACK.md)). Install the official Todoist MCP (https://developer.todoist.com/ → MCP) and register it on your platform like above. After setup you can swap Todoist for another tool — see [CUSTOMIZE.md](CUSTOMIZE.md).

## 4. The analysis skills pack (REQUIRED — auto-installed)
Six skills from **[ajeeshworkspace/indian-trading-skills](https://github.com/ajeeshworkspace/indian-trading-skills)** (MIT):
`nse-vcp-screener` · `technical-analyst` · `india-news-tracker` · `fii-dii-flow-tracker` · `india-market-breadth` · `scenario-analyzer`
The installer clones the repo and copies any missing skill dirs into `~/.claude/skills/` (Codex reads the same dir when `~/.codex/skills` is symlinked — the installer handles it).

## 5. Python 3 + screener dependencies
```bash
python3 --version          # 3.9+
pip3 install yfinance pandas niftystocks
```
On macOS with PEP-668 ("externally managed environment"), use `pip3 install --user ...` or a venv — the installer will offer.

## 6. Accounts you need
- **Groww** account with your holdings (the installer reads them to propose your plan).
- **Todoist** account (free tier is fine).
- India-market focus: NSE symbols, ₹, IST market hours are assumed (v1 scope).
