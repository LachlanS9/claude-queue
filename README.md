# claude-queue

> Fire Claude Code prompts from your phone. Pick up the results in the morning.

---

## Chronically Online Workflow

Have you ever asked yourself, how I could possibly make my Claude agents work harder? 
Why am I wasting time sleeping when I could be building my new AI-native, agentic, autonomous, multi-agent, vertically-integrated, cloud-native, enterprise-grade, API-first, workflow-orchestration, hyperautomated, category-defining, venture-scalable, product-led-growth, digitally-transformative B2B SaaS EMPIRE?

If meeting your wife's boyfriend has taught you anything about B2B sales then this is for you.

So recently I signed up to Claude Code after putting it off for ages. 
I was living off those glorious days of $10 Copilot pro subscriptions, but that was obliterated when they went from request based billing to token based billing. 

I finally bit the bullet and I was intoduced to this 5 Hour window concept. 

Every night I'd go to sleep with 4–5 hours left in my usage window and Claude would just sit there. Doing NOTHING. Slacking off. There are no free rides around here. 

So I built claude-queue. 
A TELEGRAM BOT SO I CAN FIRE OFF PROMPTS FROM MY PHONE. 

Now I can be outside touching grass while I fire claude prompts.

Literally me:
<img width="500" height="501" alt="atkvc7" src="https://github.com/user-attachments/assets/97417399-43b5-48e2-86e5-5c7c5870fab1" />


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

[![DigitalOcean Referral Badge](https://web-platforms.sfo2.cdn.digitaloceanspaces.com/WWW/Badge%201.svg)](https://www.digitalocean.com/?refcode=bd7257bb96fd&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge)

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

### Getting prompts onto the bot

Prompts are `.md` files with YAML frontmatter. Once saved, you fire them by name. There are a few ways to get them in:

**Drag into Telegram desktop (recommended for detailed prompts)**
Write your `.md` file in your editor with the codebase open, then drag it directly into the Telegram chat with your bot on Mac or Windows. The bot saves it automatically — no commands needed.

**Share sheet on iOS/Android**
On mobile, find the `.md` file in Files/Documents, tap Share, and share it to your Telegram bot chat.

**Type it directly in Telegram**
For short prompts on the go:
```
/save my-prompt-name
```
The bot asks for the content as your next message. Paste or type it, hit send.

**One-off without saving**
Skip saving entirely:
```
/run Fix the overflow on the activity list — pills wrapping below 375px
```

---

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

MIT - idk claude did this for me 
