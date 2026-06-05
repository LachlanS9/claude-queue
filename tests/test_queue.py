import time
import pytest
from job_queue import enqueue, dequeue, peek_all, set_running, clear_running, get_running, make_job


def _job(name="test-job", repo="backend"):
    return make_job(
        prompt_name=name,
        content="Do something",
        repo=repo,
        model="claude-sonnet-4-6",
        thinking="none",
        base_branch="main",
    )


def test_enqueue_dequeue(redis_client):
    job = _job()
    enqueue(redis_client, job)
    result = dequeue(redis_client)
    assert result is not None
    assert result.prompt_name == "test-job"


def test_dequeue_empty_returns_none(redis_client):
    assert dequeue(redis_client) is None


def test_dequeue_fifo(redis_client):
    enqueue(redis_client, _job("first"))
    enqueue(redis_client, _job("second"))
    assert dequeue(redis_client).prompt_name == "first"
    assert dequeue(redis_client).prompt_name == "second"


def test_peek_all_does_not_consume(redis_client):
    enqueue(redis_client, _job("a"))
    enqueue(redis_client, _job("b"))
    jobs = peek_all(redis_client)
    assert len(jobs) == 2
    assert dequeue(redis_client) is not None


def test_running_state(redis_client):
    assert get_running(redis_client) is None
    job = _job()
    set_running(redis_client, job)
    running = get_running(redis_client)
    assert running is not None
    assert running.prompt_name == "test-job"
    clear_running(redis_client)
    assert get_running(redis_client) is None


def test_make_job_assigns_unique_id():
    j1 = _job()
    j2 = _job()
    assert j1.id != j2.id


def test_scheduled_job_preserves_timestamp(redis_client):
    future = time.time() + 3600
    job = make_job("sched", "content", "backend", "claude-sonnet-4-6", "none", "main", scheduled_at=future)
    enqueue(redis_client, job)
    result = dequeue(redis_client)
    assert abs(result.scheduled_at - future) < 1


def test_make_job_includes_submitted_by():
    job = make_job(
        prompt_name="test",
        content="do something",
        repo="backend",
        model="claude-sonnet-4-6",
        thinking="none",
        base_branch="main",
        submitted_by=99999,
    )
    assert job.submitted_by == 99999


def test_job_roundtrip_preserves_submitted_by(redis_client):
    job = make_job("p", "c", "backend", "claude-sonnet-4-6", "none", "main", submitted_by=42)
    enqueue(redis_client, job)
    result = dequeue(redis_client)
    assert result.submitted_by == 42


def test_job_roundtrip_defaults_submitted_by(redis_client):
    job = make_job("p", "c", "backend", "claude-sonnet-4-6", "none", "main")
    enqueue(redis_client, job)
    result = dequeue(redis_client)
    assert result.submitted_by == 0
