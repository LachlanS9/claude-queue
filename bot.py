import json
import os
import time
from typing import Dict, List, Optional, Tuple
import frontmatter as fm
import redis as redis_lib
from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from job_queue import enqueue, peek_all, get_running, request_cancel, make_job
from prompt_loader import list_prompts, get_prompt, resolve, PROMPTS_SUBDIR, MODEL_MAP
from usage import query_since, summarise_by_model
from scheduler import parse_brisbane_time, minutes_until

_ALIAS = {
    "claude-haiku-4-5-20251001": "haiku",
    "claude-sonnet-4-6": "sonnet",
    "claude-opus-4-7": "opus",
}
_SAVE_PENDING_KEY = "claude_queue:save_pending:{user_id}"

_HELP_TEXT = (
    "*Claude Queue — Command Reference*\n\n"
    "*Prompts*\n"
    "/list — All saved prompts (name, repo, model, first line)\n"
    "/view <name> — Full prompt with variable docs\n"
    "/save <name> — Save a new prompt (bot asks for content next)\n"
    "/delete <name> — Delete a saved prompt\n"
    "Send a .md file — Bot saves it automatically\n\n"
    "*Running jobs*\n"
    "/fire <name> [Key=Value...] — Queue one or more prompts\n"
    "/run [--model haiku|sonnet|opus] [--thinking none|low|medium|high] [--repo backend|frontend] [--branch <name>] <text>\n"
    "/dryrun <name> [Key=Value...] — Preview resolved prompt without queuing\n"
    "/schedule <name> <HH:MM> [Key=Value...] — Fire at a Brisbane local time today\n"
    "/status — Show running job and pending queue\n"
    "/cancel — Stop the currently running job\n\n"
    "*Usage*\n"
    "/usage — Token usage since last reset, broken down by model\n"
    "/resettime <HH:MM> — Change the daily usage reset time (Brisbane)\n"
    "/log — Last 5 completed jobs with token counts\n\n"
    "*Models* (set in prompt frontmatter or via --model)\n"
    "haiku — Fast, cheap · sonnet — Standard (default) · opus — Complex tasks\n\n"
    "*Thinking levels* (set in prompt frontmatter or via --thinking)\n"
    "none · low · medium · high"
)


def is_allowed(user_id: int, user_accounts: Dict[int, str]) -> bool:
    return user_id in user_accounts


def parse_fire_args(args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    names, kv = [], {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            kv[k] = v
        else:
            names.append(arg)
    return names, kv


def parse_run_args(args: List[str]) -> Tuple[str, str, str, str, str]:
    model = MODEL_MAP["sonnet"]
    thinking = "none"
    repo = "backend"
    branch = "main"
    remaining = []
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = MODEL_MAP.get(args[i + 1], MODEL_MAP["sonnet"])
            i += 2
        elif args[i] == "--thinking" and i + 1 < len(args):
            thinking = args[i + 1]
            i += 2
        elif args[i] == "--repo" and i + 1 < len(args):
            repo = args[i + 1]
            i += 2
        elif args[i] == "--branch" and i + 1 < len(args):
            branch = args[i + 1]
            i += 2
        else:
            remaining.append(args[i])
            i += 1
    return model, thinking, repo, branch, " ".join(remaining)


def format_prompt_list(prompts) -> str:
    if not prompts:
        return "No prompts found. Send a .md file to the bot or use /save <name>."
    lines = []
    for p in prompts:
        alias = _ALIAS.get(p.model, p.model)
        first_line = p.content.split("\n")[0][:60]
        var_hint = f" [{','.join(p.vars.keys())}]" if p.vars else ""
        lines.append(f"• {p.name}{var_hint} ({p.repo}, {alias}) — {first_line}")
    return "\n".join(lines)


def format_usage_summary(summary: dict, minutes_until_reset: int, reset_time: str) -> str:
    if not summary:
        return f"No usage recorded since last reset.\nReset at {reset_time} ({minutes_until_reset} min away)"
    lines = [f"Usage since {reset_time} reset:"]
    for model, stats in summary.items():
        alias = _ALIAS.get(model, model)
        j = stats["jobs"]
        lines.append(f"  {alias} — {j} job{'s' if j != 1 else ''} · {stats['input_tokens']:,} in / {stats['output_tokens']:,} out")
    lines.append(f"Reset in {minutes_until_reset} min ({reset_time})")
    return "\n".join(lines)


def format_status(r: redis_lib.Redis) -> str:
    running = get_running(r)
    pending = peek_all(r)
    if not running and not pending:
        return "Queue is idle."
    lines = []
    if running:
        lines.append(f"Running:  {running.prompt_name} (base: {running.base_branch})")
    for job in pending:
        sched = " [scheduled]" if job.scheduled_at else ""
        lines.append(f"Pending:  {job.prompt_name}{sched}")
    return "\n".join(lines)


def save_prompt_content(name: str, content: str, backend_path: str) -> str:
    try:
        post = fm.loads(content)
        repo = str(post.get("repo", "backend"))
    except Exception:
        repo = "backend"
    dest_dir = os.path.join(backend_path, PROMPTS_SUBDIR, repo)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{name}.md")
    with open(dest, "w") as f:
        f.write(content)
    return dest


def delete_prompt(name: str, backend_path: str) -> bool:
    root = os.path.join(backend_path, PROMPTS_SUBDIR)
    for dirpath, _, files in os.walk(root):
        for fname in files:
            if os.path.splitext(fname)[0] == name:
                os.remove(os.path.join(dirpath, fname))
                return True
    return False


def make_command_handlers(config: Config, r: redis_lib.Redis):
    backend_path = config.backend_repo_path

    def _guard(user_id: int) -> bool:
        return is_allowed(user_id, config.user_accounts)

    async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        await update.message.reply_text(format_prompt_list(list_prompts(backend_path)))

    async def cmd_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /view <name>")
            return
        p = get_prompt(context.args[0], backend_path)
        if p is None:
            await update.message.reply_text(f"Prompt '{context.args[0]}' not found. Run /list.")
            return
        alias = _ALIAS.get(p.model, p.model)
        var_lines = "\n".join(f"  {k}: {v}" for k, v in p.vars.items()) if p.vars else "  (none)"
        await update.message.reply_text(
            f"{p.name}\nRepo: {p.repo} | Model: {alias} | Thinking: {p.thinking} | Base: {p.base_branch}\nVars:\n{var_lines}\n\n{p.content}"
        )

    async def cmd_fire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /fire <name> [name2...] [Key=Value...]")
            return
        names, kv = parse_fire_args(context.args)
        if not names:
            await update.message.reply_text("No prompt names provided.")
            return
        queued = []
        for name in names:
            p = get_prompt(name, backend_path)
            if p is None:
                await update.message.reply_text(f"Prompt '{name}' not found.")
                continue
            content, _ = resolve(p, kv)
            enqueue(r, make_job(p.name, content, p.repo, p.model, p.thinking, p.base_branch,
                                submitted_by=update.effective_user.id))
            queued.append(name)
        if queued:
            await update.message.reply_text(f"Queued: {', '.join(queued)}")

    async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text(
                "Usage: /run [--model haiku|sonnet|opus] [--thinking none|low|medium|high] "
                "[--repo backend|frontend] [--branch <name>] <prompt text>"
            )
            return
        model, thinking, repo, branch, text = parse_run_args(list(context.args))
        if not text:
            await update.message.reply_text("No prompt text provided after flags.")
            return
        enqueue(r, make_job("custom", text, repo, model, thinking, branch,
                            submitted_by=update.effective_user.id))
        alias = _ALIAS.get(model, model)
        await update.message.reply_text(f"Custom prompt queued ({alias}, thinking: {thinking}, repo: {repo}, branch: {branch}).")

    async def cmd_dryrun(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /dryrun <name> [Key=Value...]")
            return
        name = context.args[0]
        _, kv = parse_fire_args(list(context.args[1:]))
        p = get_prompt(name, backend_path)
        if p is None:
            await update.message.reply_text(f"Prompt '{name}' not found.")
            return
        content, missing = resolve(p, kv)
        if missing:
            await update.message.reply_text(f"Missing variables: {', '.join(missing)}")
            return
        alias = _ALIAS.get(p.model, p.model)
        preview = f"[DRY RUN] {name}\nModel: {alias} | Thinking: {p.thinking} | Base: {p.base_branch}\n\n{content[:800]}"
        if len(content) > 800:
            preview += f"\n... ({len(content) - 800} more chars)"
        await update.message.reply_text(preview)

    async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /schedule <name> <HH:MM> [Key=Value...]")
            return
        name, hhmm = context.args[0], context.args[1]
        _, kv = parse_fire_args(list(context.args[2:]))
        p = get_prompt(name, backend_path)
        if p is None:
            await update.message.reply_text(f"Prompt '{name}' not found.")
            return
        content, missing = resolve(p, kv)
        if missing:
            await update.message.reply_text(f"Missing variables: {', '.join(missing)}")
            return
        try:
            fire_at = parse_brisbane_time(hhmm)
        except ValueError:
            await update.message.reply_text("Invalid time. Use HH:MM e.g. 09:05")
            return
        enqueue(r, make_job(p.name, content, p.repo, p.model, p.thinking, p.base_branch,
                            scheduled_at=fire_at, submitted_by=update.effective_user.id))
        await update.message.reply_text(f"'{name}' scheduled for {hhmm} Brisbane time.")

    async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /save <name> — then send your prompt content as the next message.")
            return
        name = context.args[0]
        key = _SAVE_PENDING_KEY.format(user_id=update.effective_user.id)
        r.set(key, name, ex=300)
        await update.message.reply_text(
            f"Ready to save '{name}'. Send the prompt content now (include frontmatter if needed).\n"
            f"Defaults: repo=backend, model=sonnet, thinking=none, base-branch=main"
        )

    async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /delete <name>")
            return
        name = context.args[0]
        if delete_prompt(name, backend_path):
            await update.message.reply_text(f"Deleted '{name}'.")
        else:
            await update.message.reply_text(f"Prompt '{name}' not found.")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        await update.message.reply_text(format_status(r))

    async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if get_running(r) is None:
            await update.message.reply_text("Nothing is currently running.")
            return
        request_cancel(r)
        await update.message.reply_text("Cancel requested. The running job will stop shortly.")

    async def cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        config_path = os.path.expanduser("~/bot-config.json")
        with open(config_path) as f:
            cfg_data = json.load(f)
        reset_time = cfg_data.get("reset_time", "09:00")
        reset_ts = parse_brisbane_time(reset_time)
        rows = query_since(config.usage_db_path, reset_ts - 86400)
        summary = summarise_by_model(rows)
        await update.message.reply_text(format_usage_summary(summary, minutes_until(reset_ts), reset_time))

    async def cmd_resettime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        if not context.args:
            await update.message.reply_text("Usage: /resettime <HH:MM>")
            return
        hhmm = context.args[0]
        try:
            h, m = map(int, hhmm.split(":"))
            assert 0 <= h <= 23 and 0 <= m <= 59
        except (ValueError, AssertionError):
            await update.message.reply_text("Invalid time. Use HH:MM e.g. 09:00")
            return
        config_path = os.path.expanduser("~/bot-config.json")
        with open(config_path) as f:
            data = json.load(f)
        data["reset_time"] = hhmm
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
        await update.message.reply_text(f"Reset time updated to {hhmm} Brisbane local.")

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        await update.message.reply_text(_HELP_TEXT, parse_mode="Markdown")

    async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        rows = query_since(config.usage_db_path, 0)
        if not rows:
            await update.message.reply_text("No completed jobs yet.")
            return
        lines = []
        from datetime import datetime
        from zoneinfo import ZoneInfo
        for row in reversed(rows[-5:]):
            dt = datetime.fromtimestamp(row.timestamp, ZoneInfo("Australia/Brisbane")).strftime("%d/%m %H:%M")
            alias = _ALIAS.get(row.model, row.model)
            lines.append(f"[{dt}] {row.prompt_name} ({row.repo}, {alias}) — {row.input_tokens:,}in/{row.output_tokens:,}out")
        await update.message.reply_text("\n".join(lines))

    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        doc = update.message.document
        if not doc.file_name.endswith(".md"):
            await update.message.reply_text("Please send a .md file.")
            return
        name = os.path.splitext(doc.file_name)[0]
        tg_file = await context.bot.get_file(doc.file_id)
        content_bytes = await tg_file.download_as_bytearray()
        content = content_bytes.decode("utf-8")
        path = save_prompt_content(name, content, backend_path)
        repo = "backend" if "backend" in path else "frontend"
        await update.message.reply_text(f"✓ Saved '{name}' ({repo}). Ready to /fire.")

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _guard(update.effective_user.id): return
        user_id = update.effective_user.id
        key = _SAVE_PENDING_KEY.format(user_id=user_id)
        pending_name = r.get(key)
        if not pending_name:
            return
        r.delete(key)
        content = update.message.text
        path = save_prompt_content(pending_name, content, backend_path)
        repo = "backend" if "backend" in path else "frontend"
        await update.message.reply_text(f"✓ Saved '{pending_name}' ({repo}). Ready to /fire.")

    return {
        "commands": {
            "help": cmd_help,
            "list": cmd_list,
            "view": cmd_view,
            "fire": cmd_fire,
            "run": cmd_run,
            "dryrun": cmd_dryrun,
            "schedule": cmd_schedule,
            "save": cmd_save,
            "delete": cmd_delete,
            "status": cmd_status,
            "cancel": cmd_cancel,
            "usage": cmd_usage,
            "resettime": cmd_resettime,
            "log": cmd_log,
        },
        "document": handle_document,
        "text": handle_text,
    }
