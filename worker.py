import json
import os
import pwd
import re
import subprocess
import time
from typing import Callable, Dict
import redis

from config import Config
from job_queue import (
    Job, dequeue, enqueue, make_job, set_running, clear_running,
    peek_all, is_cancel_requested, clear_cancel,
)
from pr import create_pr
from usage import init_db, record, UsageRow


class RateLimitError(Exception):
    pass


class CancelledError(Exception):
    pass


class NoChangesError(Exception):
    pass


def run_worker(config: Config, send_telegram: Callable[[str], None], r: redis.Redis) -> None:
    init_db(config.usage_db_path)
    while True:
        job = dequeue(r)
        if job is None:
            time.sleep(2)
            continue

        if job.scheduled_at and job.scheduled_at > time.time():
            enqueue(r, job)
            time.sleep(30)
            continue

        set_running(r, job)
        try:
            result = run_job(job, config, r)
            record(config.usage_db_path, UsageRow(
                timestamp=time.time(),
                prompt_name=job.prompt_name,
                repo=job.repo,
                model=job.model,
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
            ))
            msg = (
                f"✓ {job.prompt_name} done — {result['pr_url']}\n"
                f"Model: {_model_alias(job.model)} · Thinking: {job.thinking} · Base: {job.base_branch}\n"
                f"Tokens: {result['input_tokens']:,} in / {result['output_tokens']:,} out"
            )
            send_telegram(msg)
        except RateLimitError:
            delayed = make_job(
                prompt_name=job.prompt_name,
                content=job.prompt_content,
                repo=job.repo,
                model=job.model,
                thinking=job.thinking,
                base_branch=job.base_branch,
                scheduled_at=time.time() + 1800,
                submitted_by=job.submitted_by,
            )
            enqueue(r, delayed)
            send_telegram(f"⚠️ {job.prompt_name} hit rate limit — requeued in 30 min")
        except NoChangesError:
            send_telegram(f"ℹ️ {job.prompt_name} — Claude made no changes. Refine the prompt or add more detail.")
        except CancelledError:
            send_telegram(f"❌ {job.prompt_name} was cancelled")
        except Exception as e:
            send_telegram(f"✗ {job.prompt_name} failed: {str(e)[:200]}")
        finally:
            clear_running(r)
            clear_cancel(r)

        if not peek_all(r):
            send_telegram("All done — queue is empty.")


def run_job(job: Job, config: Config, r: redis.Redis = None) -> Dict:
    system_user = config.user_accounts.get(job.submitted_by)
    if not system_user:
        raise RuntimeError(f"No system account mapped for submitted_by={job.submitted_by}. Add this user to user_accounts in bot-config.json.")

    repo_path = config.repos.get(job.repo)
    if not repo_path:
        raise RuntimeError(f"Unknown repo '{job.repo}'. Add it to repos in bot-config.json.")

    worktree = f"/tmp/cq-{job.id}"
    branch = f"queue/{int(time.time())}-{_slug(job.prompt_name)}"

    subprocess.run(
        ["git", "-C", repo_path, "fetch", "origin", job.base_branch],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo_path, "worktree", "add", worktree, "-b", branch, f"origin/{job.base_branch}"],
        check=True, capture_output=True,
    )

    try:
        pw = pwd.getpwnam(system_user)
        subprocess.run(["chown", "-R", system_user, worktree], check=True)

        env = os.environ.copy()
        env["HOME"] = pw.pw_dir

        def _drop_privs():
            os.setgid(pw.pw_gid)
            os.setuid(pw.pw_uid)

        process = subprocess.Popen(
            ["claude", "--dangerously-skip-permissions", "--model", job.model, "--output-format", "json", "-p", job.prompt_content],
            cwd=worktree,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=_drop_privs,
        )

        while process.poll() is None:
            if r and is_cancel_requested(r):
                process.terminate()
                raise CancelledError()
            time.sleep(2)

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            if "rate limit" in stderr.lower() or "rate limit" in stdout.lower():
                raise RateLimitError()
            raise RuntimeError(f"claude exited {process.returncode}: {stderr[:300]}")

        input_tokens, output_tokens = _parse_usage(stdout)

        subprocess.run(["chown", "-R", "root:root", worktree], check=True)
        _auto_commit(worktree, job.prompt_name)

        if not _has_changes_to_push(worktree, job.base_branch):
            raise NoChangesError()

        subprocess.run(
            ["git", "-C", worktree, "push", "origin", branch],
            check=True, capture_output=True,
        )

        pr_url = create_pr(config, job, branch)
        return {"pr_url": pr_url, "input_tokens": input_tokens, "output_tokens": output_tokens}

    finally:
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "remove", "--force", worktree],
            capture_output=True,
        )


def _auto_commit(worktree: str, prompt_name: str) -> None:
    status = subprocess.run(
        ["git", "-C", worktree, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if status.stdout.strip():
        subprocess.run(["git", "-C", worktree, "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", worktree, "commit", "-m", f"feat: {prompt_name}"],
            check=True, capture_output=True,
        )


def _has_changes_to_push(worktree: str, base_branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", worktree, "log", f"origin/{base_branch}..HEAD", "--oneline"],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def _parse_usage(stdout: str):
    try:
        data = json.loads(stdout)
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", usage.get("inputTokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("outputTokens", 0))
        return input_tokens, output_tokens
    except (json.JSONDecodeError, AttributeError):
        return 0, 0


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", name.lower())[:40]


def _model_alias(model_id: str) -> str:
    return {
        "claude-haiku-4-5-20251001": "haiku",
        "claude-sonnet-4-6": "sonnet",
        "claude-opus-4-7": "opus",
    }.get(model_id, model_id)
