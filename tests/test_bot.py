import os
import textwrap
import pytest
import fakeredis
from unittest.mock import AsyncMock, MagicMock, patch
from bot import (
    is_allowed, parse_fire_args, parse_run_args,
    format_prompt_list, format_usage_summary, format_status, save_prompt_content,
)
from job_queue import make_job, enqueue, set_running
from usage import UsageRow


def test_is_allowed_permits_mapped_user():
    assert is_allowed(user_id=123, user_accounts={123: "cq-alice", 456: "cq-bob"}) is True


def test_is_allowed_blocks_unmapped_user():
    assert is_allowed(user_id=999, user_accounts={123: "cq-alice"}) is False


def test_parse_fire_args_names_and_vars():
    names, kv = parse_fire_args(["auth-refactor", "stripe-fix", "Resource=Note", "id=noteId"])
    assert names == ["auth-refactor", "stripe-fix"]
    assert kv == {"Resource": "Note", "id": "noteId"}


def test_parse_fire_args_names_only():
    names, kv = parse_fire_args(["auth-refactor"])
    assert names == ["auth-refactor"]
    assert kv == {}


def test_parse_fire_args_empty():
    names, kv = parse_fire_args([])
    assert names == []
    assert kv == {}


def test_parse_run_args_defaults():
    model, thinking, repo, branch, text = parse_run_args(["fix", "the", "overflow"])
    assert model == "claude-sonnet-4-6"
    assert thinking == "none"
    assert repo is None
    assert branch == "main"
    assert text == "fix the overflow"


def test_parse_run_args_all_flags():
    args = ["--model", "opus", "--thinking", "high", "--repo", "frontend", "--branch", "epic/x", "do", "something"]
    model, thinking, repo, branch, text = parse_run_args(args)
    assert model == "claude-opus-4-7"
    assert thinking == "high"
    assert repo == "frontend"
    assert branch == "epic/x"
    assert text == "do something"


def test_parse_run_args_partial_flags():
    args = ["--model", "haiku", "quick", "fix"]
    model, thinking, repo, branch, text = parse_run_args(args)
    assert model == "claude-haiku-4-5-20251001"
    assert thinking == "none"
    assert text == "quick fix"


def test_format_prompt_list():
    from prompt_loader import Prompt
    prompts = [
        Prompt("auth-refactor", "backend", "claude-sonnet-4-6", "none", "main", {}, "Refactor the auth service here."),
        Prompt("add-endpoint", "backend", "claude-opus-4-7", "high", "main", {"Resource": "desc"}, "Add a {{Resource}} endpoint."),
    ]
    text = format_prompt_list(prompts)
    assert "auth-refactor" in text
    assert "sonnet" in text
    assert "opus" in text
    assert "add-endpoint" in text


def test_format_usage_summary_empty():
    text = format_usage_summary({}, minutes_until_reset=120, reset_time="09:00")
    assert "No usage" in text


def test_format_usage_summary_with_data():
    summary = {
        "claude-sonnet-4-6": {"jobs": 3, "input_tokens": 24000, "output_tokens": 8000},
    }
    text = format_usage_summary(summary, minutes_until_reset=40, reset_time="09:00")
    assert "sonnet" in text
    assert "3 job" in text
    assert "24,000" in text


def test_format_status_empty(redis_client):
    text = format_status(redis_client)
    assert "idle" in text.lower()


def test_format_status_with_running_and_pending(redis_client):
    running = make_job("auth-refactor", "content", "backend", "claude-sonnet-4-6", "none", "main", submitted_by=1)
    set_running(redis_client, running)
    pending = make_job("stripe-fix", "content", "backend", "claude-sonnet-4-6", "none", "main", submitted_by=1)
    enqueue(redis_client, pending)
    text = format_status(redis_client)
    assert "auth-refactor" in text
    assert "stripe-fix" in text


def test_save_prompt_content_writes_file(tmp_path):
    content = textwrap.dedent("""
        ---
        repo: backend
        model: sonnet
        ---
        Do something useful.
    """).strip()
    path = save_prompt_content("my-prompt", content, str(tmp_path))
    assert os.path.exists(path)
    assert "backend" in path
    assert "my-prompt.md" in path
    with open(path) as f:
        assert "Do something useful" in f.read()


def test_save_prompt_content_uses_frontend_dir(tmp_path):
    content = "---\nrepo: frontend\n---\nDo something."
    path = save_prompt_content("ui-thing", content, str(tmp_path))
    assert "frontend" in path


def test_save_prompt_content_defaults_to_default_repo(tmp_path):
    content = "Just a plain prompt with no frontmatter."
    path = save_prompt_content("plain", content, str(tmp_path))
    assert "default" in path


def test_delete_prompt_file(tmp_path):
    from bot import delete_prompt
    content = "---\nrepo: backend\n---\nContent."
    save_prompt_content("to-delete", content, str(tmp_path))
    assert delete_prompt("to-delete", str(tmp_path)) is True
    assert delete_prompt("to-delete", str(tmp_path)) is False
