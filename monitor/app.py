from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


STATIC_DIR = Path(__file__).resolve().parent / "static"


@dataclass(frozen=True)
class MonitorConfig:
    output_dir: Path
    host: str
    port: int

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        root = Path(os.getenv("PROJECT_ROOT", "/workspace")).resolve()
        return cls(
            output_dir=Path(os.getenv("OUTPUT_DIR", str(root / "pipeline_output"))).resolve(),
            host=os.getenv("MONITOR_HOST", "0.0.0.0"),
            port=int(os.getenv("MONITOR_PORT", "8000")),
        )


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
    except OSError:
        return []
    return records


def path_basename(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return Path(value).name


def iso_sort_key(value: object) -> str:
    return value if isinstance(value, str) else ""


def summarize_record(record: dict) -> dict:
    message = record.get("message")
    if not isinstance(message, dict):
        message = {}

    sample_id = message.get("sample_id") or record.get("sample_id")
    classification = message.get("classification") or record.get("classification")
    video_filename = path_basename(message.get("video_path"))
    result_filename = path_basename(message.get("result_path"))

    return {
        "sample_id": sample_id,
        "classification": classification,
        "topic": record.get("topic"),
        "consumed_at": record.get("consumed_at"),
        "produced_at": message.get("produced_at"),
        "classified_at": message.get("classified_at"),
        "task_name": message.get("task_name"),
        "dataset_file": message.get("dataset_file"),
        "demo_key": message.get("demo_key"),
        "use_actions": message.get("use_actions"),
        "playback_ok": message.get("playback_ok"),
        "success": message.get("success"),
        "duration_seconds": message.get("duration_seconds"),
        "video_filename": video_filename,
        "video_url": f"/videos/{video_filename}" if video_filename else None,
        "result_filename": result_filename,
        "metadata_url": f"/api/metadata/{sample_id}" if sample_id else None,
    }


def load_records(output_dir: Path) -> list[dict]:
    records = []
    for classification in ("success", "failure"):
        records.extend(read_jsonl(output_dir / "logs" / f"{classification}.jsonl"))
    records.sort(
        key=lambda item: iso_sort_key(item.get("consumed_at") or item.get("produced_at")),
        reverse=True,
    )
    return records


def load_samples(output_dir: Path, classification: str = "all", limit: int = 200) -> list[dict]:
    samples = [summarize_record(record) for record in load_records(output_dir)]
    if classification in {"success", "failure"}:
        samples = [sample for sample in samples if sample.get("classification") == classification]
    return samples[:limit]


def build_task_stats(samples: list[dict]) -> dict:
    by_task: dict[str, dict[str, int]] = {}
    for sample in samples:
        task = str(sample.get("task_name") or "unknown")
        classification = sample.get("classification")
        current = by_task.setdefault(task, {"total": 0, "success": 0, "failure": 0})
        current["total"] += 1
        if classification in {"success", "failure"}:
            current[classification] += 1
    return dict(sorted(by_task.items()))


def load_stats(output_dir: Path) -> dict:
    stats = read_json(
        output_dir / "stats.json",
        {"total": 0, "success": 0, "failure": 0, "last_sample_id": None, "last_updated_at": None},
    )
    if not isinstance(stats, dict):
        stats = {"total": 0, "success": 0, "failure": 0, "last_sample_id": None, "last_updated_at": None}

    all_samples = load_samples(output_dir, limit=10_000)
    total = int(stats.get("total", 0) or 0)
    success = int(stats.get("success", 0) or 0)
    stats["success_rate"] = round(success / total, 4) if total else 0.0
    stats["by_task"] = build_task_stats(all_samples)
    stats["recent_samples"] = all_samples[:10]
    return stats


def find_metadata(output_dir: Path, sample_id: str) -> dict | None:
    for classification in ("success", "failure"):
        path = output_dir / "metadata" / classification / f"{sample_id}.json"
        item = read_json(path, None)
        if isinstance(item, dict):
            return item

    for record in load_records(output_dir):
        message = record.get("message")
        if isinstance(message, dict) and message.get("sample_id") == sample_id:
            return record
    return None


def safe_child_path(root: Path, requested_name: str) -> Path | None:
    relative = Path(unquote(requested_name))
    if not relative.name or relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


class MonitorHandler(BaseHTTPRequestHandler):
    config: MonitorConfig

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"monitor {self.address_string()} - {fmt % args}", flush=True)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return

        ctype = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                self.wfile.write(chunk)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/samples":
            query = parse_qs(parsed.query)
            classification = query.get("classification", ["all"])[0]
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                limit = 200
            limit = max(1, min(limit, 10_000))
            self.send_json(load_samples(self.config.output_dir, classification, limit))
            return

        if path == "/api/stats":
            self.send_json(load_stats(self.config.output_dir))
            return

        if path.startswith("/api/metadata/"):
            sample_id = unquote(path.removeprefix("/api/metadata/")).strip()
            metadata = find_metadata(self.config.output_dir, sample_id)
            if metadata is None:
                self.send_error(HTTPStatus.NOT_FOUND.value)
                return
            self.send_json(metadata)
            return

        if path.startswith("/videos/"):
            video_path = safe_child_path(self.config.output_dir / "videos", path.removeprefix("/videos/"))
            if video_path is None:
                self.send_error(HTTPStatus.BAD_REQUEST.value)
                return
            self.send_file(video_path, "video/mp4")
            return

        if path == "/":
            self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        static_path = safe_child_path(STATIC_DIR, path.removeprefix("/"))
        if static_path is not None and static_path.exists():
            self.send_file(static_path)
            return

        self.send_error(HTTPStatus.NOT_FOUND.value)


def main() -> None:
    config = MonitorConfig.from_env()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    MonitorHandler.config = config
    server = ThreadingHTTPServer((config.host, config.port), MonitorHandler)
    print(
        json.dumps(
            {
                "event": "monitor_started",
                "host": config.host,
                "port": config.port,
                "output_dir": str(config.output_dir),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
