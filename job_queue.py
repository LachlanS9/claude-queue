import json
import uuid
from dataclasses import dataclass, asdict
from typing import List, Optional
import redis as redis_lib

_QUEUE_KEY = "claude_queue:jobs"
_RUNNING_KEY = "claude_queue:running"
_CANCEL_KEY = "claude_queue:cancel_requested"


@dataclass
class Job:
    id: str
    prompt_name: str
    prompt_content: str
    repo: str
    model: str
    thinking: str
    base_branch: str
    scheduled_at: Optional[float]
    submitted_by: int = 0


def make_job(
    prompt_name: str,
    content: str,
    repo: str,
    model: str,
    thinking: str,
    base_branch: str,
    scheduled_at: Optional[float] = None,
    submitted_by: int = 0,
) -> Job:
    return Job(
        id=str(uuid.uuid4()),
        prompt_name=prompt_name,
        prompt_content=content,
        repo=repo,
        model=model,
        thinking=thinking,
        base_branch=base_branch,
        scheduled_at=scheduled_at,
        submitted_by=submitted_by,
    )


def enqueue(r: redis_lib.Redis, job: Job) -> None:
    r.rpush(_QUEUE_KEY, json.dumps(asdict(job)))


def dequeue(r: redis_lib.Redis) -> Optional[Job]:
    raw = r.lpop(_QUEUE_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    data.setdefault("submitted_by", 0)
    return Job(**data)


def peek_all(r: redis_lib.Redis) -> List[Job]:
    items = []
    for item in r.lrange(_QUEUE_KEY, 0, -1):
        data = json.loads(item)
        data.setdefault("submitted_by", 0)
        items.append(Job(**data))
    return items


def set_running(r: redis_lib.Redis, job: Job) -> None:
    r.set(_RUNNING_KEY, json.dumps(asdict(job)))


def clear_running(r: redis_lib.Redis) -> None:
    r.delete(_RUNNING_KEY)


def get_running(r: redis_lib.Redis) -> Optional[Job]:
    raw = r.get(_RUNNING_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    data.setdefault("submitted_by", 0)
    return Job(**data)


def request_cancel(r: redis_lib.Redis) -> None:
    r.set(_CANCEL_KEY, "1")


def is_cancel_requested(r: redis_lib.Redis) -> bool:
    return bool(r.get(_CANCEL_KEY))


def clear_cancel(r: redis_lib.Redis) -> None:
    r.delete(_CANCEL_KEY)
