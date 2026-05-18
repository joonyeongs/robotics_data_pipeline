from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def video_status_name(classification: str) -> str:
    return "success" if classification == "success" else "fail"


def build_video_path(video_dir: Path, task_name: str, classification: str, sample_id: str) -> Path:
    return video_dir / f"{task_name}_{video_status_name(classification)}_{sample_id}.mp4"


def finalize_video_path(temp_video_path: Path, final_video_path: Path) -> str | None:
    if not temp_video_path.exists():
        return None
    final_video_path.parent.mkdir(parents=True, exist_ok=True)
    temp_video_path.replace(final_video_path)
    return str(final_video_path)


def run_playback(
    *,
    dexmimicgen_dir: Path,
    dataset_path: Path,
    demo_key: str,
    sample_id: str,
    task_name: str,
    output_dir: Path,
    use_actions: bool,
    video_skip: int,
    timeout_seconds: int,
) -> dict:
    video_dir = output_dir / "videos"
    result_dir = output_dir / "playback_results"
    video_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    temp_video_path = video_dir / f"{sample_id}.pending.mp4"
    result_path = result_dir / f"{sample_id}.json"
    command = [
        sys.executable,
        "scripts/playback_datasets.py",
        "--dataset",
        str(dataset_path),
        "--demo-key",
        demo_key,
        "--n",
        "1",
        "--video_path",
        str(temp_video_path),
        "--result-json",
        str(result_path),
        "--video_skip",
        str(video_skip),
    ]
    if use_actions:
        command.append("--use-actions")

    env = os.environ.copy()
    env.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
    env.setdefault("MUJOCO_GL", "osmesa")

    started = time.time()
    completed = subprocess.run(
        command,
        cwd=dexmimicgen_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    duration = time.time() - started

    if completed.returncode != 0:
        final_video_path = build_video_path(video_dir, task_name, "failure", sample_id)
        video_path = finalize_video_path(temp_video_path, final_video_path)
        return {
            "success": False,
            "classification": "failure",
            "playback_ok": False,
            "playback_error": {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
            "video_path": video_path,
            "result_path": str(result_path) if result_path.exists() else None,
            "duration_seconds": duration,
        }

    with result_path.open("r", encoding="utf-8") as f:
        result = json.load(f)

    success = bool(result["success"])
    classification = "success" if success else "failure"
    final_video_path = build_video_path(video_dir, task_name, classification, sample_id)
    video_path = finalize_video_path(temp_video_path, final_video_path)
    return {
        "success": success,
        "classification": classification,
        "playback_ok": True,
        "playback_result": result,
        "video_path": video_path,
        "result_path": str(result_path),
        "duration_seconds": duration,
    }
