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
from monitor.app import find_metadata, load_samples, load_stats, safe_child_path


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


def test_monitor_summarizes_outputs(tmp_path):
    output_dir = tmp_path / "out"
    sample = {
        "sample_id": "sample-2",
        "classification": "failure",
        "produced_at": "2026-05-18T00:00:00+00:00",
        "classified_at": "2026-05-18T00:00:02+00:00",
        "dataset_file": "two_arm_box_cleanup.hdf5",
        "demo_key": "demo_3",
        "duration_seconds": 2.25,
        "playback_ok": True,
        "success": False,
        "task_name": "TwoArmBoxCleanup",
        "use_actions": True,
        "video_path": "/workspace/pipeline_output/videos/TwoArmBoxCleanup_fail_sample-2.mp4",
    }
    record = {
        "classification": "failure",
        "consumed_at": "2026-05-18T00:00:03+00:00",
        "message": sample,
        "topic": "robotics.samples.failure",
    }

    append_jsonl(output_dir / "logs" / "failure.jsonl", record)
    write_metadata(output_dir / "metadata" / "failure" / "sample-2.json", record)
    update_stats(output_dir / "stats.json", "failure", "sample-2", record["consumed_at"])

    samples = load_samples(output_dir)
    stats = load_stats(output_dir)

    assert samples[0]["sample_id"] == "sample-2"
    assert samples[0]["video_filename"] == "TwoArmBoxCleanup_fail_sample-2.mp4"
    assert samples[0]["video_url"] == "/videos/TwoArmBoxCleanup_fail_sample-2.mp4"
    assert stats["failure"] == 1
    assert stats["by_task"]["TwoArmBoxCleanup"]["failure"] == 1
    assert find_metadata(output_dir, "sample-2") == record


def test_monitor_safe_child_path_blocks_traversal(tmp_path):
    root = tmp_path / "videos"
    root.mkdir()
    assert safe_child_path(root, "demo.mp4") == (root / "demo.mp4").resolve()
    assert safe_child_path(root, "../demo.mp4") is None
