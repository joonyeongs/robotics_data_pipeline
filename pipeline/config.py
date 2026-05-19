from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


SUCCESS_TOPIC = "robotics.samples.success"
FAILURE_TOPIC = "robotics.samples.failure"


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class PipelineConfig:
    bootstrap_servers: str
    dataset_dir: Path
    output_dir: Path
    dexmimicgen_dir: Path
    interval_seconds: float
    max_samples: int
    producer_client_id: str
    success_topic: str
    failure_topic: str
    video_skip: int
    playback_timeout_seconds: int
    kafka_connect_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        root = Path(os.getenv("PROJECT_ROOT", "/workspace")).resolve()
        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            dataset_dir=Path(
                os.getenv(
                    "DATASET_DIR",
                    str(root / "data" / "playback_data"),
                )
            ).resolve(),
            output_dir=Path(os.getenv("OUTPUT_DIR", str(root / "pipeline_output"))).resolve(),
            dexmimicgen_dir=Path(
                os.getenv("DEXMIMICGEN_DIR", str(root / "robots" / "dexmimicgen"))
            ).resolve(),
            interval_seconds=_float_env("PRODUCER_INTERVAL_SECONDS", 5.0),
            max_samples=_int_env("MAX_SAMPLES", 10),
            producer_client_id=os.getenv("PRODUCER_CLIENT_ID", "robotics-sample-producer"),
            success_topic=os.getenv("SUCCESS_TOPIC", SUCCESS_TOPIC),
            failure_topic=os.getenv("FAILURE_TOPIC", FAILURE_TOPIC),
            video_skip=_int_env("VIDEO_SKIP", 5),
            playback_timeout_seconds=_int_env("PLAYBACK_TIMEOUT_SECONDS", 900),
            kafka_connect_timeout_seconds=_int_env("KAFKA_CONNECT_TIMEOUT_SECONDS", 60),
        )


@dataclass(frozen=True)
class ConsumerConfig:
    bootstrap_servers: str
    output_dir: Path
    topic: str
    classification: str
    group_id: str
    max_messages: int
    kafka_connect_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "ConsumerConfig":
        root = Path(os.getenv("PROJECT_ROOT", "/workspace")).resolve()
        classification = os.getenv("CLASSIFICATION", "success")
        default_topic = SUCCESS_TOPIC if classification == "success" else FAILURE_TOPIC
        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            output_dir=Path(os.getenv("OUTPUT_DIR", str(root / "pipeline_output"))).resolve(),
            topic=os.getenv("TOPIC", default_topic),
            classification=classification,
            group_id=os.getenv("CONSUMER_GROUP_ID", f"robotics-{classification}-consumer"),
            max_messages=_int_env("MAX_MESSAGES", 0),
            kafka_connect_timeout_seconds=_int_env("KAFKA_CONNECT_TIMEOUT_SECONDS", 60),
        )
