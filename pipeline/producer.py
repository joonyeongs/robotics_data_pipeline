from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from kafka.errors import NoBrokersAvailable
from kafka import KafkaProducer

from pipeline.config import PipelineConfig
from pipeline.hdf5_sampling import choose_demo_key, choose_hdf5_file, choose_use_actions, get_task_name
from pipeline.playback import run_playback


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_producer(config: PipelineConfig) -> KafkaProducer:
    deadline = time.time() + config.kafka_connect_timeout_seconds
    while True:
        try:
            return KafkaProducer(
                bootstrap_servers=config.bootstrap_servers,
                client_id=config.producer_client_id,
                value_serializer=lambda value: json.dumps(value, sort_keys=True).encode("utf-8"),
                key_serializer=lambda value: value.encode("utf-8"),
                acks="all",
                retries=5,
            )
        except NoBrokersAvailable:
            if time.time() >= deadline:
                raise
            print("Kafka broker is not ready for producer yet; retrying...", flush=True)
            time.sleep(2)


def produce_once(config: PipelineConfig, producer: KafkaProducer) -> dict:
    sample_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
    dataset_seed = time.time_ns()
    dataset_path = choose_hdf5_file(config.dataset_dir, dataset_seed)
    task_name = get_task_name(dataset_path)
    demo_seed = time.time_ns()
    demo_key = choose_demo_key(dataset_path, demo_seed)
    action_seed = time.time_ns()
    use_actions = choose_use_actions(action_seed)

    message = {
        "sample_id": sample_id,
        "produced_at": utc_now(),
        "dataset_path": str(dataset_path),
        "dataset_file": dataset_path.name,
        "task_name": task_name,
        "demo_key": demo_key,
        "seeds": {
            "dataset_seed": dataset_seed,
            "demo_seed": demo_seed,
            "action_seed": action_seed,
        },
        "use_actions": use_actions,
    }

    playback = run_playback(
        dexmimicgen_dir=config.dexmimicgen_dir,
        dataset_path=dataset_path,
        demo_key=demo_key,
        sample_id=sample_id,
        task_name=task_name,
        output_dir=config.output_dir,
        use_actions=use_actions,
        video_skip=config.video_skip,
        timeout_seconds=config.playback_timeout_seconds,
    )
    message.update(playback)
    message["classified_at"] = utc_now()

    topic = config.success_topic if message["classification"] == "success" else config.failure_topic
    producer.send(topic, key=sample_id, value=message).get(timeout=30)
    producer.flush()
    print(
        json.dumps(
            {
                "event": "produced",
                "sample_id": sample_id,
                "topic": topic,
                "classification": message["classification"],
                "dataset_file": dataset_path.name,
                "task_name": task_name,
                "demo_key": demo_key,
                "use_actions": use_actions,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return message


def main() -> None:
    config = PipelineConfig.from_env()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    producer = make_producer(config)
    count = 0
    try:
        while config.max_samples == 0 or count < config.max_samples:
            started = time.time()
            produce_once(config, producer)
            count += 1
            if config.max_samples != 0 and count >= config.max_samples:
                break
            elapsed = time.time() - started
            time.sleep(max(0.0, config.interval_seconds - elapsed))
    finally:
        producer.close()


if __name__ == "__main__":
    main()
