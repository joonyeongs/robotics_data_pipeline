from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path


EMPTY_STATS = {
    "total": 0,
    "success": 0,
    "failure": 0,
    "last_sample_id": None,
    "last_updated_at": None,
}


def update_stats(stats_path: Path, classification: str, sample_id: str, updated_at: str) -> dict:
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        raw = f.read().strip()
        stats = json.loads(raw) if raw else dict(EMPTY_STATS)
        stats["total"] = int(stats.get("total", 0)) + 1
        stats[classification] = int(stats.get(classification, 0)) + 1
        stats["last_sample_id"] = sample_id
        stats["last_updated_at"] = updated_at
        f.seek(0)
        f.truncate()
        json.dump(stats, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return stats


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(json.dumps(record, sort_keys=True))
        f.write("\n")
        f.flush()
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def write_metadata(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".{time.time_ns()}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp_path.replace(path)

