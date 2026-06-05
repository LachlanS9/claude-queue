import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import frontmatter

PROMPTS_SUBDIR = os.path.join(".claude", "prompts")

MODEL_MAP: Dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}

THINKING_PREFIX: Dict[str, str] = {
    "none": "",
    "low": "think\n\n",
    "medium": "think hard\n\n",
    "high": "ultrathink\n\n",
}


@dataclass
class Prompt:
    name: str
    repo: str
    model: str
    thinking: str
    base_branch: str
    vars: Dict[str, str]
    content: str


def list_prompts(repo_path: str) -> List[Prompt]:
    root = os.path.join(repo_path, PROMPTS_SUBDIR)
    prompts = []
    if not os.path.isdir(root):
        return prompts
    for dirpath, _, files in os.walk(root):
        for fname in files:
            if fname.endswith(".md"):
                name = os.path.splitext(fname)[0]
                prompts.append(_load(name, os.path.join(dirpath, fname)))
    return sorted(prompts, key=lambda p: p.name)


def get_prompt(name: str, repo_path: str) -> Optional[Prompt]:
    root = os.path.join(repo_path, PROMPTS_SUBDIR)
    if not os.path.isdir(root):
        return None
    for dirpath, _, files in os.walk(root):
        for fname in files:
            if os.path.splitext(fname)[0] == name:
                return _load(name, os.path.join(dirpath, fname))
    return None


def resolve(prompt: Prompt, supplied: Dict[str, str]) -> Tuple[str, List[str]]:
    content = prompt.content
    for k, v in supplied.items():
        content = content.replace(f"{{{{{k}}}}}", v)
    missing = sorted(k for k in prompt.vars if k not in supplied)
    prefix = THINKING_PREFIX.get(prompt.thinking, "")
    return prefix + content, missing


def _load(name: str, path: str) -> Prompt:
    post = frontmatter.load(path)
    model_alias = str(post.get("model", "sonnet"))
    return Prompt(
        name=name,
        repo=str(post.get("repo", "default")),
        model=MODEL_MAP.get(model_alias, MODEL_MAP["sonnet"]),
        thinking=str(post.get("thinking", "none")),
        base_branch=str(post.get("base-branch", "main")),
        vars={k: str(v) for k, v in (post.get("vars") or {}).items()},
        content=post.content.strip(),
    )
