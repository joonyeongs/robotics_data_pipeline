from __future__ import annotations

import json

import h5py

from pipeline.hdf5_sampling import (
    choose_demo_key,
    choose_hdf5_file,
    get_task_name,
    list_demo_keys,
    list_hdf5_files,
    sanitize_name,
)
from pipeline.playback import build_video_path
from pipeline.stats import append_jsonl, update_stats, write_metadata


def create_dataset(path, demos, env_args=None):
    with h5py.File(path, "w") as hdf:
        data = hdf.create_group("data")
        if env_args is not None:
            data.attrs["env_args"] = env_args
        for demo in demos:
            data.create_group(demo)


def test_hdf5_sampling_is_seeded(tmp_path):
    first = tmp_path / "a.hdf5"
    second = tmp_path / "b.hdf5"
    create_dataset(first, ["demo_2", "demo_10", "demo_1"])
    create_dataset(second, ["demo_0"])

    assert list_hdf5_files(tmp_path) == [first, second]
    assert list_demo_keys(first) == ["demo_1", "demo_2", "demo_10"]
    assert choose_hdf5_file(tmp_path, 123) == choose_hdf5_file(tmp_path, 123)
    assert choose_demo_key(first, 456) == choose_demo_key(first, 456)


def test_task_name_and_video_filename(tmp_path):
    dataset = tmp_path / "two arm coffee.hdf5"
    create_dataset(dataset, ["demo_0"], env_args=json.dumps({"env_name": "TwoArm Coffee"}))

    assert sanitize_name("TwoArm Coffee!") == "TwoArm_Coffee"
    assert get_task_name(dataset) == "TwoArm_Coffee"
    assert build_video_path(tmp_path, "TwoArm_Coffee", "success", "sample-1").name == (
        "TwoArm_Coffee_success_sample-1.mp4"
    )
    assert build_video_path(tmp_path, "TwoArm_Coffee", "failure", "sample-1").name == (
        "TwoArm_Coffee_fail_sample-1.mp4"
    )


def test_stats_jsonl_and_metadata_outputs(tmp_path):
    output_dir = tmp_path / "out"
    sample = {"sample_id": "sample-1", "classification": "success"}
    record = {"message": sample}

    append_jsonl(output_dir / "logs" / "success.jsonl", record)
    write_metadata(output_dir / "metadata" / "success" / "sample-1.json", record)
    stats = update_stats(output_dir / "stats.json", "success", "sample-1", "2026-05-18T00:00:00+00:00")

    assert stats["total"] == 1
    assert stats["success"] == 1
    assert stats["failure"] == 0
    assert json.loads((output_dir / "logs" / "success.jsonl").read_text().strip()) == record
    assert json.loads((output_dir / "metadata" / "success" / "sample-1.json").read_text()) == record
