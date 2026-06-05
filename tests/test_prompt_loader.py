import os
import textwrap
import pytest
from prompt_loader import list_prompts, get_prompt, resolve, Prompt


def _write_prompt(tmp_path, subdir, name, content):
    d = tmp_path / ".claude" / "prompts" / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(textwrap.dedent(content))


def test_list_prompts_returns_all(tmp_path):
    _write_prompt(tmp_path, "backend", "auth-refactor", """
        ---
        repo: backend
        ---
        Refactor auth.
    """)
    _write_prompt(tmp_path, "frontend", "add-button", """
        ---
        repo: frontend
        model: haiku
        ---
        Add a button.
    """)
    prompts = list_prompts(str(tmp_path))
    assert len(prompts) == 2
    names = {p.name for p in prompts}
    assert names == {"auth-refactor", "add-button"}


def test_get_prompt_defaults(tmp_path):
    _write_prompt(tmp_path, "backend", "my-prompt", """
        ---
        repo: backend
        ---
        Do something.
    """)
    p = get_prompt("my-prompt", str(tmp_path))
    assert p is not None
    assert p.repo == "backend"
    assert p.model == "claude-sonnet-4-6"
    assert p.thinking == "none"
    assert p.base_branch == "main"
    assert p.vars == {}


def test_get_prompt_full_frontmatter(tmp_path):
    _write_prompt(tmp_path, "backend", "complex", """
        ---
        repo: backend
        model: opus
        thinking: high
        base-branch: epic/shadcn-rewrite
        vars:
          Resource: "Resource name e.g. Note"
          id: "ID param e.g. noteId"
        ---
        Add {{Resource}} endpoint with {{id}}.
    """)
    p = get_prompt("complex", str(tmp_path))
    assert p.model == "claude-opus-4-7"
    assert p.thinking == "high"
    assert p.base_branch == "epic/shadcn-rewrite"
    assert "Resource" in p.vars


def test_resolve_substitutes_variables(tmp_path):
    _write_prompt(tmp_path, "backend", "tmpl", """
        ---
        repo: backend
        vars:
          Resource: "Resource name"
          id: "ID param"
        ---
        Add {{Resource}} with {{id}}.
    """)
    p = get_prompt("tmpl", str(tmp_path))
    content, missing = resolve(p, {"Resource": "Note", "id": "noteId"})
    assert "Note" in content
    assert "noteId" in content
    assert missing == []


def test_resolve_partial_substitution(tmp_path):
    _write_prompt(tmp_path, "backend", "tmpl2", """
        ---
        repo: backend
        vars:
          Resource: "Resource name"
          id: "ID param"
        ---
        Add {{Resource}} with {{id}}.
    """)
    p = get_prompt("tmpl2", str(tmp_path))
    content, missing = resolve(p, {"Resource": "Note"})
    assert "Note" in content
    assert "{{id}}" in content
    assert missing == ["id"]


def test_resolve_no_vars_sends_prompt_as_is(tmp_path):
    _write_prompt(tmp_path, "backend", "tmpl3", """
        ---
        repo: backend
        vars:
          Resource: "Resource name"
        ---
        Add {{Resource}} endpoint.
    """)
    p = get_prompt("tmpl3", str(tmp_path))
    content, missing = resolve(p, {})
    assert "{{Resource}}" in content
    assert missing == ["Resource"]


def test_resolve_prepends_thinking_prefix(tmp_path):
    _write_prompt(tmp_path, "backend", "thinker", """
        ---
        repo: backend
        thinking: high
        ---
        Do a complex thing.
    """)
    p = get_prompt("thinker", str(tmp_path))
    content, _ = resolve(p, {})
    assert content.startswith("ultrathink\n\n")


def test_get_prompt_returns_none_for_unknown(tmp_path):
    result = get_prompt("nonexistent", str(tmp_path))
    assert result is None
