from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from pipeline.config import ConsumerConfig
from pipeline.stats import append_jsonl, update_stats, write_metadata


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_consumer(config: ConsumerConfig) -> KafkaConsumer:
    deadline = time.time() + config.kafka_connect_timeout_seconds
    while True:
        try:
            return KafkaConsumer(
                config.topic,
                bootstrap_servers=config.bootstrap_servers,
                group_id=config.group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
                key_deserializer=lambda value: value.decode("utf-8") if value else None,
            )
        except NoBrokersAvailable:
            if time.time() >= deadline:
                raise
            print(
                f"Kafka broker is not ready for {config.classification} consumer yet; retrying...",
                flush=True,
            )
            time.sleep(2)


def handle_message(config: ConsumerConfig, message: dict) -> dict:
    consumed_at = utc_now()
    sample_id = message["sample_id"]
    record = {
        "consumed_at": consumed_at,
        "topic": config.topic,
        "classification": config.classification,
        "message": message,
    }
    append_jsonl(config.output_dir / "logs" / f"{config.classification}.jsonl", record)
    write_metadata(
        config.output_dir / "metadata" / config.classification / f"{sample_id}.json",
        record,
    )
    stats = update_stats(
        config.output_dir / "stats.json",
        config.classification,
        sample_id,
        consumed_at,
    )
    print(
        json.dumps(
            {
                "event": "consumed",
                "sample_id": sample_id,
                "classification": config.classification,
                "stats": stats,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return record


def main() -> None:
    config = ConsumerConfig.from_env()
    consumer = make_consumer(config)
    consumed = 0
    try:
        for item in consumer:
            handle_message(config, item.value)
            consumed += 1
            if config.max_messages and consumed >= config.max_messages:
                break
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
