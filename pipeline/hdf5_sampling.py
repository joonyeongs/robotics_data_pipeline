from __future__ import annotations

import json
import random
import re
from pathlib import Path

import h5py


def list_hdf5_files(dataset_dir: Path) -> list[Path]:
    files = sorted(path for path in dataset_dir.glob("*.hdf5") if path.is_file())
    if not files:
        raise FileNotFoundError(f"No .hdf5 files found in {dataset_dir}")
    return files


def list_demo_keys(dataset_path: Path) -> list[str]:
    with h5py.File(dataset_path, "r") as hdf:
        if "data" not in hdf:
            raise ValueError(f"{dataset_path} does not contain a /data group")
        demos = sorted(
            hdf["data"].keys(),
            key=lambda name: (
                0,
                int(name.split("_", 1)[1]),
            )
            if name.startswith("demo_")
            else (1, name),
        )
    if not demos:
        raise ValueError(f"{dataset_path} contains no demos under /data")
    return demos


def choose_hdf5_file(dataset_dir: Path, seed: int) -> Path:
    files = list_hdf5_files(dataset_dir)
    return random.Random(seed).choice(files)


def choose_demo_key(dataset_path: Path, seed: int) -> str:
    demos = list_demo_keys(dataset_path)
    return random.Random(seed).choice(demos)


def choose_use_actions(seed: int) -> bool:
    return bool(random.Random(seed).getrandbits(1))


def sanitize_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    sanitized = sanitized.strip("._-")
    return sanitized or "unknown_task"


def get_task_name(dataset_path: Path) -> str:
    with h5py.File(dataset_path, "r") as hdf:
        env_args = hdf["data"].attrs.get("env_args") if "data" in hdf else None

    if isinstance(env_args, bytes):
        env_args = env_args.decode("utf-8")

    if isinstance(env_args, str):
        try:
            parsed = json.loads(env_args)
        except json.JSONDecodeError:
            parsed = {}
        env_name = parsed.get("env_name")
        if env_name:
            return sanitize_name(str(env_name))

    return sanitize_name(dataset_path.stem)
