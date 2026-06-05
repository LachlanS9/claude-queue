# Setup Guide

Everything needed to run a new instance or add a new user to an existing one.

---

## Prerequisites

- A Linux VM (tested on Ubuntu 22.04). See the README for a hosting recommendation.
- Root or sudo access.
- Your code in a Git repository (GitHub or Azure DevOps).

---

## 1. Install server dependencies

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip redis-server git nodejs npm
sudo systemctl enable redis-server && sudo systemctl start redis-server
```

Install Claude Code CLI (as root so it's available to all users):

```bash
sudo npm install -g @anthropic-ai/claude-code
```

---

## 2. Clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/claude-queue.git ~/claude-queue
cd ~/claude-queue
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Clone your code repositories

The worker creates git worktrees from these repos. Clone them onto the VM.

```bash
mkdir -p ~/repos
git clone https://github.com/YOUR_ORG/YOUR_API_REPO.git ~/repos/api
git clone https://github.com/YOUR_ORG/YOUR_WEB_REPO.git ~/repos/web
```

The VM needs push access to create branches and PRs. Use a deploy key or a PAT with read/write access to code.

---

## 4. Create system user accounts

Each person gets their own system user. The worker runs Claude under that user's account, isolated to their own Claude subscription.

```bash
sudo useradd -m -s /bin/bash cq-alice
sudo useradd -m -s /bin/bash cq-bob
```

---

## 5. Authenticate Claude for each user

Each system user must log in to their own Claude account once.

```bash
sudo -u cq-alice -i claude
```

Follow the authentication prompts (a browser link will appear — open it, sign in, paste the code back). Once done, exit with `/exit`. Repeat for each user:

```bash
sudo -u cq-bob -i claude
```

Verify:

```bash
sudo -u cq-alice claude --version
```

---

## 6. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts.
3. Copy the **HTTP API token** (format: `123456:ABC-DEF...`). This is `TELEGRAM_BOT_TOKEN`.

---

## 7. Find Telegram user IDs

Each user messages [@userinfobot](https://t.me/userinfobot) on Telegram to get their numeric user ID.

---

## 8. Set up PR access

**GitHub:**
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens.
2. Create a token with **Contents: Read & Write** and **Pull requests: Read & Write** on the relevant repos.
3. Note the token — it becomes `GITHUB_TOKEN`.
4. Note `GITHUB_REPO` as `owner/repo` (e.g. `myorg/my-api`). If you have multiple repos, the worker derives the repo name from the last path segment of the repo path in your config — it must match the actual GitHub repo name.

**Azure DevOps:**
1. Go to `https://dev.azure.com/YOUR_ORG` → avatar → Personal access tokens.
2. Create a token: Name `claude-queue`, Scopes: **Code → Read & Write**.
3. Note the token — it becomes `AZURE_DEVOPS_PAT`.

---

## 9. Configure environment variables

Create `/etc/systemd/system/claude-queue.env`:

```bash
sudo tee /etc/systemd/system/claude-queue.env > /dev/null <<'EOF'
TELEGRAM_BOT_TOKEN=123456:your-token-here

# GitHub (if using GitHub PRs)
GITHUB_TOKEN=ghp_your-token-here
GITHUB_REPO=owner/repo-name

# Azure DevOps (if using Azure DevOps PRs)
# AZURE_DEVOPS_ORG=your-org
# AZURE_DEVOPS_PROJECT=your-project
# AZURE_DEVOPS_PAT=your-pat
EOF
sudo chmod 600 /etc/systemd/system/claude-queue.env
```

---

## 10. Create `~/bot-config.json`

```bash
tee ~/bot-config.json > /dev/null <<'EOF'
{
  "user_accounts": {
    "123456789": "cq-alice",
    "987654321": "cq-bob"
  },
  "repos": {
    "api": "~/repos/api",
    "web": "~/repos/web"
  },
  "pr_provider": "github",
  "default_repo": "api",
  "reset_time": "09:00"
}
EOF
```

- `user_accounts` — Telegram user ID (string) → system username
- `repos` — repo key (used in prompt frontmatter) → absolute path on VM
- `pr_provider` — `"github"` or `"azuredevops"`
- `default_repo` — repo key used when `/run` is called without `--repo`
- `reset_time` — daily usage counter reset time (local timezone)

---

## 11. Install systemd services

```bash
sudo cp ~/claude-queue/systemd/*.service /etc/systemd/system/
sudo cp ~/claude-queue/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Edit `/etc/systemd/system/claude-queue-bot.service` to ensure it looks like this:

```ini
[Unit]
Description=Claude Queue Telegram Bot
After=network.target redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/claude-queue
EnvironmentFile=/etc/systemd/system/claude-queue.env
ExecStart=/root/claude-queue/venv/bin/python main_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Apply the same `EnvironmentFile` line to `claude-queue-worker.service` and `claude-queue-reminder.service`.

Enable and start:

```bash
sudo systemctl enable claude-queue-bot.service claude-queue-worker.service claude-queue-reminder.timer
sudo systemctl start claude-queue-bot.service claude-queue-worker.service claude-queue-reminder.timer
```

---

## 12. Verify

```bash
sudo systemctl status claude-queue-bot.service
journalctl -u claude-queue-bot.service -n 30
```

Open Telegram, find your bot, send `/help`. You should get the command reference back.

---

## Adding a new user

1. They message [@userinfobot](https://t.me/userinfobot) to get their Telegram user ID.
2. Create their system account: `sudo useradd -m -s /bin/bash cq-newperson`
3. Authenticate Claude: `sudo -u cq-newperson -i claude` → follow prompts → `/exit`
4. Add to `~/bot-config.json`:
   ```json
   {
     "user_accounts": {
       "123456789": "cq-alice",
       "111222333": "cq-newperson"
     },
     "repos": {
       "api": "~/repos/api"
     },
     "pr_provider": "github",
     "default_repo": "api",
     "reset_time": "09:00"
   }
   ```
5. Restart: `sudo systemctl restart claude-queue-bot.service`

---

## VM management

```bash
# Deploy code update
ssh your-vm "cd ~/claude-queue && git pull && systemctl restart claude-queue-bot.service claude-queue-worker.service"

# Check logs
ssh your-vm "journalctl -u claude-queue-bot.service -n 50"
ssh your-vm "journalctl -u claude-queue-worker.service -n 50"

# SSH into VM
ssh your-vm

# Switch to a user's Claude session for debugging
sudo -u cq-alice -i
claude --version
```
