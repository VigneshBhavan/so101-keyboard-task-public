# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
from pathlib import Path

from scripts.so101_homing.typing_ab_benchmark import (
    ALPHABET,
    DEFAULT_EXCLUDED_SHOWCASES,
    POLICIES,
    POLICY_ORDERS,
    generate_balanced_corpus,
    generate_counterbalanced_schedule,
    prepare_protocol_bundle,
    read_schedule,
)


def test_balanced_corpus_is_reproducible_and_covers_qwerty_transitions() -> None:
    first = generate_balanced_corpus(seed=42)
    second = generate_balanced_corpus(seed=42)

    assert first == second
    assert len(first["sequences"]) == 100
    assert len(set(first["sequences"])) == 100
    assert not set(first["sequences"]).intersection(DEFAULT_EXCLUDED_SHOWCASES)
    assert max(first["letter_counts"].values()) - min(first["letter_counts"].values()) <= 1
    assert set(first["letter_counts"]) == set(ALPHABET)
    for bucket in ("short", "medium", "long"):
        assert first["transition_counts"][bucket] > 0


def test_schedule_blocks_every_sequence_once_per_policy_and_counterbalances_order() -> None:
    corpus = generate_balanced_corpus(count=4, sequence_length=6, seed=7)
    schedule = generate_counterbalanced_schedule(corpus)

    assert schedule["trial_count"] == 12
    for block_index, sequence in enumerate(corpus["sequences"], start=1):
        rows = [row for row in schedule["rows"] if row["block_index"] == block_index]
        assert [row["sequence"] for row in rows] == [sequence] * len(POLICIES)
        assert tuple(row["policy"] for row in rows) == POLICY_ORDERS[(block_index - 1) % len(POLICY_ORDERS)]


def test_protocol_defaults_to_native_episode_contract(tmp_path: Path) -> None:
    paths = prepare_protocol_bundle(tmp_path / "benchmark", count=4, seed=11)
    protocol = json.loads(paths["protocol"].read_text())
    schedule_rows = read_schedule(paths["schedule_csv"])

    assert protocol["episode_limit_s"] is None
    assert protocol["episode_limit_source"] == "native_stage_contract"
    assert protocol["scheduled_break"] == {
        "after_complete_blocks": 20,
        "duration_s": 60.0,
        "exclude_final_block": True,
    }
    assert protocol["policy_manifests"] == {policy: None for policy in POLICIES}
    assert len(schedule_rows) == 12
