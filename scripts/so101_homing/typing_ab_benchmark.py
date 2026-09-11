# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Protocol and artifact helpers for matched physical typing benchmarks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
POLICIES = ("anchorbench", "baseline", "usd_drive")
# Rotate all six orders to balance trial position and adjacent-profile carryover.
POLICY_ORDERS = (
    ("anchorbench", "baseline", "usd_drive"),
    ("baseline", "usd_drive", "anchorbench"),
    ("usd_drive", "anchorbench", "baseline"),
    ("anchorbench", "usd_drive", "baseline"),
    ("usd_drive", "baseline", "anchorbench"),
    ("baseline", "anchorbench", "usd_drive"),
)
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_EXCLUDED_SHOWCASES = ("NVIDIA", "NEWTON")

# Row offsets approximate the physical QWERTY centers and are used only to
# audit corpus coverage. They are never policy inputs or robot targets.
_QWERTY_ROWS = (
    ("QWERTYUIOP", 0.0, 0.0),
    ("ASDFGHJKL", 0.25, 1.0),
    ("ZXCVBNM", 0.75, 2.0),
)
_QWERTY_XY = {
    letter: (offset + index, row_y) for letters, offset, row_y in _QWERTY_ROWS for index, letter in enumerate(letters)
}


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def object_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _transition_bucket(first: str, second: str) -> str:
    if first == second:
        return "repeat"
    x0, y0 = _QWERTY_XY[first]
    x1, y1 = _QWERTY_XY[second]
    distance = math.hypot(x1 - x0, y1 - y0)
    if distance <= 1.6:
        return "short"
    if distance <= 4.0:
        return "medium"
    return "long"


def corpus_statistics(sequences: Iterable[str]) -> dict[str, dict[str, int]]:
    values = list(sequences)
    letter_counts = Counter("".join(values))
    transition_counts: Counter[str] = Counter()
    for sequence in values:
        transition_counts.update(_transition_bucket(first, second) for first, second in zip(sequence, sequence[1:]))
    return {
        "letter_counts": {letter: letter_counts[letter] for letter in ALPHABET},
        "transition_counts": {bucket: transition_counts[bucket] for bucket in ("repeat", "short", "medium", "long")},
    }


def generate_balanced_corpus(
    *,
    count: int = 100,
    sequence_length: int = 6,
    seed: int = 20260719,
    excluded: Iterable[str] = DEFAULT_EXCLUDED_SHOWCASES,
) -> dict[str, Any]:
    """Generate a reproducible, nearly uniform A-Z sequence corpus."""

    if count < 1 or sequence_length < 1:
        raise ValueError("count and sequence_length must be positive")
    excluded_values = tuple(value.strip().upper() for value in excluded)
    if any(len(value) != sequence_length or not value.isascii() or not value.isalpha() for value in excluded_values):
        raise ValueError("excluded sequences must match the requested A-Z sequence length")

    slot_count = count * sequence_length
    base_count, remainder = divmod(slot_count, len(ALPHABET))
    pool = list(ALPHABET * base_count + ALPHABET[:remainder])
    rng = random.Random(seed)
    required_buckets = {"short", "medium", "long"}
    sequences: list[str] | None = None
    stats: dict[str, dict[str, int]] | None = None
    for _ in range(10_000):
        rng.shuffle(pool)
        candidate = ["".join(pool[index : index + sequence_length]) for index in range(0, slot_count, sequence_length)]
        if len(set(candidate)) != count or set(candidate).intersection(excluded_values):
            continue
        candidate_stats = corpus_statistics(candidate)
        populated = {
            bucket for bucket, bucket_count in candidate_stats["transition_counts"].items() if bucket_count > 0
        }
        if not required_buckets.issubset(populated):
            continue
        sequences = candidate
        stats = candidate_stats
        break
    if sequences is None or stats is None:
        raise RuntimeError("could not construct a valid balanced corpus")

    core = {
        "schema_version": SCHEMA_VERSION,
        "generator": "balanced_multiset_qwerty_audit_v1",
        "seed": seed,
        "sequence_count": count,
        "sequence_length": sequence_length,
        "alphabet": ALPHABET,
        "excluded_showcases": list(excluded_values),
        "sequences": sequences,
        **stats,
    }
    return {**core, "corpus_sha256": object_sha256(core)}


def generate_counterbalanced_schedule(corpus: dict[str, Any]) -> dict[str, Any]:
    sequences = list(corpus["sequences"])
    rows: list[dict[str, Any]] = []
    for block_index, sequence in enumerate(sequences, start=1):
        policy_order = POLICY_ORDERS[(block_index - 1) % len(POLICY_ORDERS)]
        for order_in_block, policy in enumerate(policy_order, start=1):
            rows.append(
                {
                    "trial_index": len(rows) + 1,
                    "trial_id": f"b{block_index:03d}-{policy}",
                    "block_id": f"b{block_index:03d}",
                    "block_index": block_index,
                    "order_in_block": order_in_block,
                    "policy": policy,
                    "sequence": sequence,
                }
            )
    core = {
        "schema_version": SCHEMA_VERSION,
        "ordering": "counterbalanced_abc_six_order_rotation",
        "policy_orders": [list(order) for order in POLICY_ORDERS],
        "corpus_sha256": corpus["corpus_sha256"],
        "trial_count": len(rows),
        "rows": rows,
    }
    return {**core, "schedule_sha256": object_sha256(core)}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _write_schedule_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = (
        "trial_index",
        "trial_id",
        "block_id",
        "block_index",
        "order_in_block",
        "policy",
        "sequence",
    )
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def prepare_protocol_bundle(
    output_dir: Path,
    *,
    count: int = 100,
    sequence_length: int = 6,
    seed: int = 20260719,
    episode_limit_s: float | None = None,
    break_every_blocks: int = 20,
    break_duration_s: float = 60.0,
) -> dict[str, Path]:
    """Write immutable corpus, schedule, and protocol artifacts."""

    if episode_limit_s is not None and episode_limit_s <= 0.0:
        raise ValueError("episode_limit_s must be positive when provided")
    if break_every_blocks < 1:
        raise ValueError("break_every_blocks must be positive")
    if break_duration_s <= 0.0:
        raise ValueError("break_duration_s must be positive")
    output_dir.mkdir(parents=True, exist_ok=False)
    corpus = generate_balanced_corpus(count=count, sequence_length=sequence_length, seed=seed)
    schedule = generate_counterbalanced_schedule(corpus)

    corpus_path = output_dir / "corpus.json"
    schedule_json_path = output_dir / "schedule.json"
    schedule_csv_path = output_dir / "schedule.csv"
    protocol_path = output_dir / "protocol.json"
    _write_json(corpus_path, corpus)
    _write_json(schedule_json_path, schedule)
    _write_schedule_csv(schedule_csv_path, schedule["rows"])

    protocol = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "so101_typing_anchorbench_vs_workshop_vs_usd_drive",
        "stage": "p1d",
        "strict_success": "exact A-Z key-down/up sequence plus the checkpoint clearance contract; no correction",
        "episode_limit_s": episode_limit_s,
        "episode_limit_source": "explicit_protocol" if episode_limit_s is not None else "native_stage_contract",
        "scheduled_break": {
            "after_complete_blocks": break_every_blocks,
            "duration_s": break_duration_s,
            "exclude_final_block": True,
        },
        "showcase_sequences": list(DEFAULT_EXCLUDED_SHOWCASES),
        "corpus": {"path": corpus_path.name, "sha256": file_sha256(corpus_path)},
        "schedule": {
            "json_path": schedule_json_path.name,
            "json_sha256": file_sha256(schedule_json_path),
            "csv_path": schedule_csv_path.name,
            "csv_sha256": file_sha256(schedule_csv_path),
        },
        "policy_manifests": {policy: None for policy in POLICIES},
    }
    _write_json(protocol_path, protocol)
    return {
        "output_dir": output_dir,
        "corpus": corpus_path,
        "schedule_json": schedule_json_path,
        "schedule_csv": schedule_csv_path,
        "protocol": protocol_path,
    }


def read_schedule(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="ascii") as handle:
        return list(csv.DictReader(handle))
