import time
import pytest
import tempfile
import os
from usage import init_db, record, query_since, summarise_by_model, UsageRow


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "usage.db")
    init_db(path)
    return path


def test_record_and_query(db_path):
    now = time.time()
    record(db_path, UsageRow(
        timestamp=now,
        prompt_name="auth-refactor",
        repo="backend",
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=200,
    ))
    rows = query_since(db_path, now - 1)
    assert len(rows) == 1
    assert rows[0].prompt_name == "auth-refactor"
    assert rows[0].input_tokens == 1000


def test_query_since_filters_old_rows(db_path):
    old_time = time.time() - 3600
    new_time = time.time()
    record(db_path, UsageRow(old_time, "old", "backend", "claude-sonnet-4-6", 100, 20))
    record(db_path, UsageRow(new_time, "new", "backend", "claude-sonnet-4-6", 200, 40))
    rows = query_since(db_path, new_time - 1)
    assert len(rows) == 1
    assert rows[0].prompt_name == "new"


def test_summarise_by_model():
    rows = [
        UsageRow(1, "a", "backend", "claude-sonnet-4-6", 1000, 200),
        UsageRow(2, "b", "backend", "claude-sonnet-4-6", 500, 100),
        UsageRow(3, "c", "frontend", "claude-opus-4-7", 2000, 400),
    ]
    summary = summarise_by_model(rows)
    assert summary["claude-sonnet-4-6"]["jobs"] == 2
    assert summary["claude-sonnet-4-6"]["input_tokens"] == 1500
    assert summary["claude-opus-4-7"]["jobs"] == 1
    assert summary["claude-opus-4-7"]["output_tokens"] == 400


def test_empty_db_returns_no_rows(db_path):
    rows = query_since(db_path, 0)
    assert rows == []
