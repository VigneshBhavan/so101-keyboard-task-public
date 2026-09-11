# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.so101_homing.typing_ab_benchmark import prepare_protocol_bundle
from scripts.so101_homing.typing_ab_execution import (
    _normalized_recipe,
    _validate_resume_session,
    _validate_benchmark_scope,
    _validate_matched_policies,
    build_runner_command,
    classify_runner_result,
    pending_schedule_rows,
    read_runner_summary,
    scheduled_break_after_row,
    verify_protocol_bundle,
)


def _policy(label: str, *, checkpoint_sha256: str) -> dict:
    return {
        "label": label,
        "stage": "p1d",
        "task_profile": "physical-calibrated-20260718",
        "normalized_task_contract": (
            "physical_calibrated_20260718_fixed_cartesian_{actuator}_p1d_transit15_letters6_v0"
        ),
        "matched_recipe_sha256": "recipe",
        "checkpoint": {
            "path": f"/{label}.pt",
            "sha256": checkpoint_sha256,
        },
        "environment": {
            "path": f"/{label}.yaml",
            "task_contract": f"physical_{label}_p1d",
            "keyboard_profile": "mx_keys_powered_az_20260718",
            "episode_length_s": 61.0,
            "clearance_m": 0.015,
            "clearance_control_ticks": 2,
            "letter_length": [6, 6],
        },
    }


def test_protocol_bundle_hash_verification_detects_edits(tmp_path: Path) -> None:
    paths = prepare_protocol_bundle(tmp_path / "protocol", count=4, seed=8)

    verified = verify_protocol_bundle(paths["output_dir"])
    assert verified["schedule_csv"] == paths["schedule_csv"].resolve()

    paths["schedule_csv"].write_text(paths["schedule_csv"].read_text() + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_protocol_bundle(paths["output_dir"])


def test_recipe_normalization_ignores_only_actuator_payload_and_labels() -> None:
    anchor = {
        "seed": "42",
        "log_dir": "/rank0/logs",
        "actuator_profile": "anchorbench",
        "task_contract": "task_anchorbench_p1d",
        "scene": {"num_envs": "2048", "robot": {"actuators": {"all": {"stiffness": "48"}}}},
        "sim": {"device": "cuda:0", "dt": "0.01"},
        "commands": {"typing": {"clearance_m": "0.015"}},
    }
    baseline = {
        **anchor,
        "seed": "43",
        "log_dir": "/rank1/logs",
        "actuator_profile": "baseline",
        "task_contract": "task_baseline_p1d",
        "scene": {"num_envs": "1024", "robot": {"actuators": {"all": {"stiffness": "usd"}}}},
        "sim": {"device": "cuda:1", "dt": "0.01"},
    }

    assert _normalized_recipe(anchor) == _normalized_recipe(baseline)
    baseline["commands"] = {"typing": {"clearance_m": "0.004"}}
    assert _normalized_recipe(anchor) != _normalized_recipe(baseline)


def test_policy_set_requires_identical_recipe_and_distinct_checkpoints() -> None:
    policies = {
        "anchorbench": _policy("anchorbench", checkpoint_sha256="a"),
        "baseline": _policy("baseline", checkpoint_sha256="b"),
        "usd_drive": _policy("usd_drive", checkpoint_sha256="c"),
    }
    _validate_matched_policies(policies)

    policies["baseline"]["environment"]["clearance_m"] = 0.004
    with pytest.raises(ValueError, match="clearance_m"):
        _validate_matched_policies(policies)

    policies["baseline"]["environment"]["clearance_m"] = 0.015
    policies["usd_drive"]["checkpoint"]["sha256"] = "a"
    with pytest.raises(ValueError, match="distinct checkpoint"):
        _validate_matched_policies(policies)


def test_benchmark_scope_requires_physical_p1d_six_letter_protocol(tmp_path: Path) -> None:
    paths = prepare_protocol_bundle(tmp_path / "protocol", count=4, sequence_length=6, seed=8)
    bundle = verify_protocol_bundle(paths["output_dir"])

    _validate_benchmark_scope(
        bundle,
        stage="p1d",
        task_profile="physical-calibrated-20260718",
    )
    with pytest.raises(ValueError, match="does not match protocol"):
        _validate_benchmark_scope(
            bundle,
            stage="p1c",
            task_profile="physical-calibrated-20260718",
        )
    with pytest.raises(ValueError, match="requires physical-calibrated"):
        _validate_benchmark_scope(bundle, stage="p1d", task_profile="legacy-fixed-cartesian")


def test_runner_command_omits_external_cutoff_by_default(tmp_path: Path) -> None:
    policy = _policy("anchorbench", checkpoint_sha256="a")
    command = build_runner_command(
        python=Path("/env/bin/python"),
        policy=policy,
        target="NVIDIA",
        out=tmp_path / "trial.jsonl",
        rest_pose=Path("/rest.json"),
        device="/dev/input/keyboard",
        port="/dev/serial/robot",
        robot_id="my_follower",
        enable_robot=True,
        episode_limit_s=None,
    )

    assert "--max-duration" not in command
    assert command[-2:] == ["--enable-robot", "--yes"]
    assert command[command.index("--expected-actuator-profile") + 1] == "anchorbench"
    assert command[command.index("--startup-mode") + 1] == "fixed-reset"


def test_runner_summary_accepts_fixed_cartesian_handoff_record(tmp_path: Path) -> None:
    path = tmp_path / "runner.jsonl"
    path.write_text(
        '{"kind":"deployment_contract"}\n'
        '{"kind":"so101_fixed_cartesian_handoff","status":"dry_run_ready"}\n',
        encoding="ascii",
    )

    assert read_runner_summary(path) == {
        "kind": "so101_fixed_cartesian_handoff",
        "status": "dry_run_ready",
    }


def test_scheduled_break_occurs_after_each_twentieth_complete_nonfinal_block() -> None:
    protocol = {
        "scheduled_break": {
            "after_complete_blocks": 20,
            "duration_s": 60.0,
            "exclude_final_block": True,
        }
    }

    assert scheduled_break_after_row(
        {"block_index": "20", "order_in_block": "3"}, protocol, total_blocks=100
    )
    assert not scheduled_break_after_row(
        {"block_index": "20", "order_in_block": "2"}, protocol, total_blocks=100
    )
    assert not scheduled_break_after_row(
        {"block_index": "21", "order_in_block": "3"}, protocol, total_blocks=100
    )
    assert not scheduled_break_after_row(
        {"block_index": "100", "order_in_block": "3"}, protocol, total_blocks=100
    )


def test_resume_skips_scored_trials_but_retries_invalid_trial_id() -> None:
    rows = [
        {"trial_id": "b001-anchorbench", "policy": "anchorbench"},
        {"trial_id": "b001-baseline", "policy": "baseline"},
        {"trial_id": "b001-usd_drive", "policy": "usd_drive"},
    ]
    attempts = [
        {"trial_id": "b001-anchorbench", "policy": "anchorbench", "mode": "robot", "result": "pass"},
        {"trial_id": "b001-baseline", "policy": "baseline", "mode": "robot", "result": "fail"},
        {"trial_id": "b001-usd_drive", "policy": "usd_drive", "mode": "robot", "result": "invalid"},
    ]

    assert pending_schedule_rows(rows, attempts, enable_robot=True) == [rows[2]]


def test_resume_rejects_changed_session_contract(tmp_path: Path) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "session.json").write_text(
        '{"mode":"robot","benchmark_manifest_sha256":"abc"}\n', encoding="ascii"
    )

    with pytest.raises(ValueError, match="benchmark_manifest_sha256"):
        _validate_resume_session(
            session_dir,
            {"mode": "robot", "benchmark_manifest_sha256": "different"},
        )


@pytest.mark.parametrize(
    ("exit_code", "summary", "dry_run", "expected"),
    (
        (0, {"status": "completed", "exact_match": True}, False, "pass"),
        (2, {"status": "stopped", "policy_started_at_unix_s": 1.0}, False, "fail"),
        (2, {"status": "fixed_reset_rejected"}, False, "invalid"),
        (0, {"status": "dry_run_ready"}, True, "software_validated"),
        (1, None, False, "invalid"),
    ),
)
def test_runner_result_classification(
    exit_code: int,
    summary: dict | None,
    dry_run: bool,
    expected: str,
) -> None:
    assert classify_runner_result(exit_code, summary, dry_run=dry_run) == expected
