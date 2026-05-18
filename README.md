# Robotics Kafka Data Pipeline

This project runs a classroom-friendly robotics data pipeline with Kafka.

The producer samples one DexMimicGen HDF5 trajectory, replays it, classifies it as
success or failure, and publishes the record to a matching Kafka topic. The two
consumers write JSONL logs, per-sample metadata, and aggregate statistics.

## Layout

- `pipeline/`: producer, consumer, HDF5 sampling, playback, and stats code.
- `vendor/dexmimicgen/`: vendored DexMimicGen code used by the replay command.
- `vendor/robosuite/`: vendored robosuite source and simulator assets used by DexMimicGen.
- `docker-compose.yml`: Kafka, topic initializer, producer, success consumer, failure consumer.
- `pipeline_output/`: generated videos, logs, metadata, and `stats.json`.

## GitHub Portability

This repository is intended to be cloned and run on different machines. Keep
machine-specific data out of git:

- Commit source code, Docker files, docs, tests, `.env.example`, and vendored
  source dependencies needed by the Docker image.
- Do not commit `.env`, `data/`, `pipeline_output/`, or large HDF5 datasets.
- Share the HDF5 dataset separately through cloud storage, a lab server, or Git
  LFS if the files must be versioned.

Each user configures their local dataset path by copying `.env.example`:

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
DATASET_HOST_DIR=/absolute/path/to/playback_data
```

`DATASET_HOST_DIR` must point to a directory containing the `.hdf5` playback
files. The directory is mounted read-only into the producer container.

## Tutorial: Run Step By Step

The default Compose command starts only the shared Kafka environment. It does
not start the producer or consumers. This keeps the tutorial observable: each
pipeline role is launched from its own terminal when students are ready.

### 1. Start Kafka and Create Topics

```bash
docker compose up --build
```

Leave this terminal open. It starts:

- `kafka`: the broker.
- `kafka-init`: a short-lived topic setup container that creates
  `robotics.samples.success` and `robotics.samples.failure`.

At this point, no robotics data is produced and no logs are written.

### 2. Build The Pipeline App Image

Open a second terminal:

```bash
cd /path/to/boaz_data_pipeline
docker compose --profile apps build
```

This prepares the Python environment used by the producer and consumers without
running them.

### 3. Start The Success Consumer

In the second terminal, run:

```bash
docker compose run --rm success-consumer
```

This consumer subscribes to `robotics.samples.success` and writes successful
sample logs and metadata.

### 4. Start The Failure Consumer

Open a third terminal:

```bash
cd /path/to/boaz_data_pipeline
docker compose run --rm failure-consumer
```

This consumer subscribes to `robotics.samples.failure` and writes failed sample
logs and metadata.

### 5. Start The Producer

Open a fourth terminal:

```bash
cd /path/to/boaz_data_pipeline
docker compose run --rm producer
```

The producer samples one HDF5 trajectory, replays it, classifies it, and sends
the message to the success or failure topic. By default, it emits 10 samples and
waits 5 seconds between sample starts.

Useful overrides:

```bash
MAX_SAMPLES=2 docker compose run --rm producer
MAX_SAMPLES=0 docker compose run --rm producer
PRODUCER_INTERVAL_SECONDS=1 MAX_SAMPLES=3 docker compose run --rm producer
```

`MAX_SAMPLES=0` means continuous production until stopped.

### 6. Inspect The Pipeline Outputs

As samples are consumed, inspect these files from the host machine:

```bash
tail -f pipeline_output/logs/success.jsonl
tail -f pipeline_output/logs/failure.jsonl
cat pipeline_output/stats.json
```

Stop the tutorial with `Ctrl+C` in the producer and consumer terminals. Stop the
Kafka environment from the first terminal with `Ctrl+C`, or from another
terminal with:

```bash
docker compose down
```

### Optional: Run All App Services Together

For demos where step-by-step observation is not needed, the producer and
consumers are available behind the `apps` Compose profile:

```bash
docker compose --profile apps up --build
```

## Outputs

- `pipeline_output/videos/{task_name}_{success|fail}_{sample_id}.mp4`
- `pipeline_output/playback_results/{sample_id}.json`
- `pipeline_output/logs/success.jsonl`
- `pipeline_output/logs/failure.jsonl`
- `pipeline_output/metadata/success/{sample_id}.json`
- `pipeline_output/metadata/failure/{sample_id}.json`
- `pipeline_output/stats.json`

Replay failures are routed to the failure topic with command output included in
the message, so environment/rendering problems are visible in the same pipeline.

## Local Tests

```bash
python -m pytest tests
```

These tests cover the local pipeline logic without starting Kafka or MuJoCo.

## Publishing To GitHub

From this directory:

```bash
git init
git add .
git status
git commit -m "Add robotics Kafka data pipeline tutorial"
git branch -M main
git remote add origin git@github.com:<your-user-or-org>/<repo-name>.git
git push -u origin main
```

Before pushing, check the staged files carefully. The repo is large because it
contains vendored simulator source. If you do not want that in git, replace
`vendor/dexmimicgen` and `vendor/robosuite` with documented install steps or
Git submodules before the first commit.
