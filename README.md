# claude-queue

> Fire Claude Code prompts from your phone. Pick up the results in the morning.

---

## Why I built this

I kept wasting my Claude subscription.

Every night I'd go to sleep with 4–5 hours left in my usage window and Claude would just sit there. During the day I'd think of things I wanted it to work on — refactors, bug fixes, features — but I was away from my desk. Commuting, in meetings, out running. By the time I got back, the window had reset and I'd missed it.

I also wanted to be able to queue work from anywhere. Not just from my desk with VS Code open — from my phone, from a café, from wherever an idea hit me. I wanted to send Claude a task, go to sleep, and wake up to pull requests.

So I built claude-queue.

---

## What it does

claude-queue is a Telegram bot that runs on a cheap Linux VM. You send it a prompt from your phone. It queues the job, runs [Claude Code](https://claude.ai/code) against your codebase when a slot opens up, pushes the changes to a new git branch, and opens a pull request. You review the PR when you're ready.

```
Your phone (Telegram)
     ↓  /fire my-prompt
Telegram Bot (VM)
     ↓  enqueues job
Redis Queue (VM)
     ↓  worker picks it up
Worker (VM)
     ↓  git worktree → claude --output-format json -p "..."
     ↓  git push branch
     ↓  GitHub / Azure DevOps REST API → create PR
Telegram notification with PR link
```

Three systemd services run permanently on the VM: `claude-queue-bot`, `claude-queue-worker`, and `claude-queue-reminder` (daily usage reset reminder).

---

## Prerequisites

- A **Claude Code subscription** (Max plan recommended for heavier usage)
- A **Linux VM** — see recommended host below
- A **Telegram account** and a bot token from [@BotFather](https://t.me/BotFather)
- Your code in **Git** (GitHub or Azure DevOps)

---

## Recommended host

[DigitalOcean](https://m.do.co/c/bd7257bb96fd) is what I use. A $6/month Basic Droplet (1 vCPU, 1 GB RAM, Ubuntu 22.04) is more than enough to run the bot, worker, and Redis.

**[Get $200 in credit for 60 days](https://m.do.co/c/bd7257bb96fd)** — enough to run this for months at no cost.

---

## Quick setup

See [`docs/setup.md`](docs/setup.md) for the full step-by-step guide. The short version:

1. Provision a Linux VM (Ubuntu 22.04)
2. Install Claude Code CLI, Redis, Python 3.11
3. Clone your code repos onto the VM
4. Create a system user per team member, authenticate each with Claude
5. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
6. Set environment variables and `~/bot-config.json`
7. Install and start the systemd services
8. Send `/help` to your bot

---

## Writing prompts

Prompts are Markdown files with YAML frontmatter, stored in a `prompts/` directory on the VM. The bot can save them for you — just upload a `.md` file or use `/save`.

### Frontmatter reference

```markdown
---
repo: api                  # required — must match a key in your repos config
model: sonnet              # optional — haiku | sonnet (default) | opus
thinking: none             # optional — none (default) | low | medium | high
base-branch: main          # optional — branch to fork from and PR into (default: main)
vars:
  Feature: "Description shown in /view and /dryrun"
  ResourceName: "Another variable"
---

Your prompt here. Use {{Feature}} and {{ResourceName}} as placeholders.
```

### Model guide

| Value | Use for |
|---|---|
| `haiku` | Quick fixes, small additions, renaming |
| `sonnet` | Standard feature work — most tasks (default) |
| `opus` | Complex refactors, architecture, multi-file rewrites |

### Thinking levels

| Value | Effect | Use for |
|---|---|---|
| `none` | No thinking prefix (default) | Routine tasks |
| `low` | Prepends "think" | Tasks with non-obvious tradeoffs |
| `medium` | Prepends "think hard" | Architecture decisions |
| `high` | Prepends "ultrathink" | Major refactors, subtle bugs |

---

## Telegram commands

| Command | Description |
|---|---|
| `/help` | Full command reference |
| `/list` | All saved prompts — name, repo, model, first line |
| `/view <name>` | Full prompt including variable descriptions |
| `/fire <name> [name2…] [Key=Value…]` | Queue one or more prompts |
| `/run [--model haiku\|sonnet\|opus] [--thinking none\|low\|medium\|high] [--repo <name>] [--branch <name>] <text>` | Queue a one-off inline prompt |
| `/dryrun <name> [Key=Value…]` | Preview resolved prompt without queuing |
| `/schedule <name> <HH:MM> [Key=Value…]` | Schedule for a local time today |
| `/save <name>` | Save a new prompt — bot asks for content next |
| `/delete <name>` | Delete a saved prompt |
| `/status` | Running job and pending queue |
| `/cancel` | Stop the currently running job |
| `/usage` | Token usage since last reset, by model |
| `/resettime <HH:MM>` | Change the daily usage reset time |
| `/log` | Last 5 completed jobs with token counts |

---

## Workflow

### Fire a saved prompt

```
/fire add-endpoint Resource=Invoice id=invoiceId
```

### Queue multiple prompts in sequence

```
/fire fix-bug add-tests update-docs
```

### Fire a quick one-off

```
/run Fix the pagination bug — it skips every other page when filtering by status
/run --model opus --thinking high Redesign the caching layer for concurrent writes
```

### Schedule overnight

```
/schedule big-refactor 02:00
```

### Variables — supply or leave blank

Supply a value to substitute before sending to Claude:
```
/fire add-endpoint Resource=Note id=noteId
```

Leave it blank and Claude infers from the codebase:
```
/fire add-endpoint
```

---

## Security

- Access is controlled by `user_accounts` in `~/bot-config.json`. Each entry maps a Telegram user ID to a system username. Messages from any unlisted user are silently ignored.
- Each user's jobs run under their own system account using their own Claude subscription. One person's rate limits cannot affect another's.
- No secrets are stored in this repository — all tokens and keys are loaded from environment variables at runtime.
- Claude runs with `--dangerously-skip-permissions` to allow headless file editing. This is necessary for autonomous operation; the VM is the trust boundary.

---

## Contributing

Issues and PRs welcome. If you add a new PR provider (GitLab, Bitbucket), follow the pattern in `pr/github.py` and open a PR.

---

## Licence

MIT
