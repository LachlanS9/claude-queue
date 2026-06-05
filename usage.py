import sqlite3
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class UsageRow:
    timestamp: float
    prompt_name: str
    repo: str
    model: str
    input_tokens: int
    output_tokens: int


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                timestamp    REAL    NOT NULL,
                prompt_name  TEXT    NOT NULL,
                repo         TEXT    NOT NULL,
                model        TEXT    NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL
            )
        """)


def record(db_path: str, row: UsageRow) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage VALUES (?,?,?,?,?,?)",
            (row.timestamp, row.prompt_name, row.repo, row.model, row.input_tokens, row.output_tokens),
        )


def query_since(db_path: str, since: float) -> List[UsageRow]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT timestamp,prompt_name,repo,model,input_tokens,output_tokens FROM usage WHERE timestamp >= ? ORDER BY timestamp",
            (since,),
        ).fetchall()
    return [UsageRow(*r) for r in rows]


def summarise_by_model(rows: List[UsageRow]) -> Dict[str, Dict]:
    summary: Dict[str, Dict] = {}
    for row in rows:
        if row.model not in summary:
            summary[row.model] = {"jobs": 0, "input_tokens": 0, "output_tokens": 0}
        summary[row.model]["jobs"] += 1
        summary[row.model]["input_tokens"] += row.input_tokens
        summary[row.model]["output_tokens"] += row.output_tokens
    return summary
