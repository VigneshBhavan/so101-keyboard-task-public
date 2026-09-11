# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Manifest validation and resumable execution for physical typing A/B/C trials."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .fixed_cartesian_policy import STAGE_TARGET_LENGTHS, FixedCartesianPolicy, deployment_profile
from .run_fixed_cartesian_policy_handoff import _validated_training_environment
from .typing_ab_benchmark import POLICIES, file_sha256, object_sha256, read_schedule

BENCHMARK_MANIFEST_NAME = "benchmark_manifest.json"
ATTEMPTS_NAME = "attempts.jsonl"
EVENTS_NAME = "events.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"could not parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def verify_protocol_bundle(root: Path) -> dict[str, Any]:
    protocol_path = root / "protocol.json"
    protocol = _read_json(protocol_path)
    for name, metadata in (
        ("corpus", protocol["corpus"]),
        ("schedule_json", protocol["schedule"]),
    ):
        path_key = "path" if name == "corpus" else "json_path"
        hash_key = "sha256" if name == "corpus" else "json_sha256"
        artifact_path = root / metadata[path_key]
        actual = file_sha256(artifact_path)
        if actual != metadata[hash_key]:
            raise ValueError(f"{artifact_path} hash mismatch: expected {metadata[hash_key]}, got {actual}")
    schedule_csv = root / protocol["schedule"]["csv_path"]
    if file_sha256(schedule_csv) != protocol["schedule"]["csv_sha256"]:
        raise ValueError(f"{schedule_csv} hash mismatch")
    return {
        "root": root.resolve(),
        "protocol_path": protocol_path.resolve(),
        "protocol_sha256": file_sha256(protocol_path),
        "protocol": protocol,
        "schedule_csv": schedule_csv.resolve(),
    }


def _normalized_recipe(config: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(config)
    value.pop("actuator_profile", None)
    value.pop("task_contract", None)
    # These values are rank-local serialization details, not task semantics.
    # The matched training runs used 4,096 global environments and base seed 1307 for all
    # profiles even though each rank wrote its own env count, seed, and device.
    value.pop("log_dir", None)
    value.pop("seed", None)
    try:
        value["scene"]["robot"]["actuators"] = "<matched-actuator-profile>"
        value["scene"]["num_envs"] = "<per-rank-environments>"
        value["sim"]["device"] = "<rank-device>"
    except (KeyError, TypeError) as exc:
        raise ValueError("environment YAML is missing required scene/simulator fields") from exc
    return value


def _normalized_task_contract(task_contract: str) -> str:
    return re.sub(r"_(anchorbench|baseline|usd_drive)_", "_{actuator}_", task_contract, count=1)


def build_policy_manifest(
    *,
    label: str,
    checkpoint: Path,
    env_config: Path,
    stage: str,
    task_profile: str,
) -> dict[str, Any]:
    if label not in POLICIES:
        raise ValueError(f"policy label must be one of {POLICIES}, got {label!r}")
    profile = deployment_profile(task_profile)
    config = _read_yaml_mapping(env_config)
    task_contract = str(config.get("task_contract", ""))
    policy = FixedCartesianPolicy(checkpoint)
    environment = _validated_training_environment(
        checkpoint=checkpoint,
        env_config=env_config,
        profile=profile,
        stage=stage,
        expected_actuator_profile=label,
        expected_task_contract=task_contract,
    )
    if environment is None:
        raise ValueError("physical A/B/C benchmark requires a validated calibrated environment")
    return {
        "schema_version": 1,
        "label": label,
        "stage": stage,
        "task_profile": task_profile,
        "checkpoint": {
            "path": str(checkpoint.resolve()),
            "sha256": policy.sha256,
            "size_bytes": checkpoint.stat().st_size,
            "iteration": policy.iteration,
            "contract": policy.contract.as_dict(),
        },
        "environment": environment,
        "normalized_task_contract": _normalized_task_contract(task_contract),
        "matched_recipe_sha256": object_sha256(_normalized_recipe(config)),
    }


def _validate_matched_policies(policies: dict[str, dict[str, Any]]) -> None:
    if set(policies) != set(POLICIES):
        raise ValueError(f"benchmark requires exactly {POLICIES}")
    checkpoint_hashes = {policy["checkpoint"]["sha256"] for policy in policies.values()}
    if len(checkpoint_hashes) != len(POLICIES):
        raise ValueError("every actuator profile must use a distinct checkpoint")
    reference = policies[POLICIES[0]]
    for label in POLICIES[1:]:
        candidate = policies[label]
        for field in ("stage", "task_profile", "normalized_task_contract", "matched_recipe_sha256"):
            if reference[field] != candidate[field]:
                raise ValueError(f"policy manifests are not matched on {field}")
        for field in (
            "keyboard_profile",
            "episode_length_s",
            "clearance_m",
            "clearance_control_ticks",
            "letter_length",
        ):
            if reference["environment"][field] != candidate["environment"][field]:
                raise ValueError(f"policy environments are not matched on {field}")


def _validate_benchmark_scope(bundle: dict[str, Any], *, stage: str, task_profile: str) -> None:
    if task_profile != "physical-calibrated-20260718":
        raise ValueError("the physical A/B/C benchmark requires physical-calibrated-20260718")
    protocol_stage = str(bundle["protocol"].get("stage", ""))
    if stage != protocol_stage:
        raise ValueError(f"benchmark stage {stage!r} does not match protocol stage {protocol_stage!r}")
    expected_length = STAGE_TARGET_LENGTHS.get(stage)
    if expected_length is None:
        raise ValueError(f"unsupported physical benchmark stage: {stage}")
    corpus_path = bundle["root"] / bundle["protocol"]["corpus"]["path"]
    sequence_length = int(_read_json(corpus_path)["sequence_length"])
    if sequence_length != expected_length:
        raise ValueError(f"benchmark corpus length {sequence_length} does not match {stage} length {expected_length}")


def finalize_benchmark_manifest(
    protocol_dir: Path,
    *,
    anchor_checkpoint: Path,
    anchor_env_config: Path,
    baseline_checkpoint: Path,
    baseline_env_config: Path,
    usd_drive_checkpoint: Path,
    usd_drive_env_config: Path,
    stage: str = "p1d",
    task_profile: str = "physical-calibrated-20260718",
) -> Path:
    bundle = verify_protocol_bundle(protocol_dir)
    _validate_benchmark_scope(bundle, stage=stage, task_profile=task_profile)
    output_path = protocol_dir / BENCHMARK_MANIFEST_NAME
    if output_path.exists():
        raise FileExistsError(f"refusing to replace frozen benchmark manifest: {output_path}")
    policies = {
        "anchorbench": build_policy_manifest(
            label="anchorbench",
            checkpoint=anchor_checkpoint,
            env_config=anchor_env_config,
            stage=stage,
            task_profile=task_profile,
        ),
        "baseline": build_policy_manifest(
            label="baseline",
            checkpoint=baseline_checkpoint,
            env_config=baseline_env_config,
            stage=stage,
            task_profile=task_profile,
        ),
        "usd_drive": build_policy_manifest(
            label="usd_drive",
            checkpoint=usd_drive_checkpoint,
            env_config=usd_drive_env_config,
            stage=stage,
            task_profile=task_profile,
        ),
    }
    _validate_matched_policies(policies)
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_path": str(bundle["protocol_path"]),
        "protocol_sha256": bundle["protocol_sha256"],
        "schedule_csv": str(bundle["schedule_csv"]),
        "schedule_sha256": file_sha256(bundle["schedule_csv"]),
        "policies": policies,
    }
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return output_path


def load_benchmark_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path)
    protocol_path = Path(manifest["protocol_path"])
    if file_sha256(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("benchmark protocol changed after policy manifests were frozen")
    schedule_path = Path(manifest["schedule_csv"])
    if file_sha256(schedule_path) != manifest["schedule_sha256"]:
        raise ValueError("benchmark schedule changed after policy manifests were frozen")
    for policy in manifest["policies"].values():
        checkpoint = Path(policy["checkpoint"]["path"])
        env_config = Path(policy["environment"]["path"])
        if file_sha256(checkpoint) != policy["checkpoint"]["sha256"]:
            raise ValueError(f"checkpoint changed after freeze: {checkpoint}")
        if file_sha256(env_config) != policy["environment"]["sha256"]:
            raise ValueError(f"environment changed after freeze: {env_config}")
    _validate_matched_policies(manifest["policies"])
    return manifest


def build_runner_command(
    *,
    python: Path,
    policy: dict[str, Any],
    target: str,
    out: Path,
    rest_pose: Path,
    device: str,
    port: str,
    robot_id: str,
    enable_robot: bool,
    episode_limit_s: float | None,
) -> list[str]:
    command = [
        str(python),
        "-m",
        "scripts.so101_homing.run_fixed_cartesian_policy_handoff",
        "--stage",
        policy["stage"],
        "--target",
        target,
        "--task-profile",
        policy["task_profile"],
        "--checkpoint",
        policy["checkpoint"]["path"],
        "--env-config",
        policy["environment"]["path"],
        "--expected-actuator-profile",
        policy["label"],
        "--expected-task-contract",
        policy["environment"]["task_contract"],
        "--rest-pose",
        str(rest_pose),
        "--startup-mode",
        "fixed-reset",
        "--device",
        device,
        "--port",
        port,
        "--id",
        robot_id,
        "--out",
        str(out),
    ]
    if enable_robot:
        command.extend(("--enable-robot", "--yes"))
    else:
        command.append("--dry-run")
    if episode_limit_s is not None:
        command.extend(("--max-duration", str(episode_limit_s)))
    return command


def read_runner_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    summary = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("kind") in {"summary", "so101_fixed_cartesian_handoff"}:
            summary = record
    return summary


def classify_runner_result(exit_code: int, summary: dict[str, Any] | None, *, dry_run: bool) -> str:
    if summary is None:
        return "invalid"
    if dry_run:
        return "software_validated" if exit_code == 0 and summary.get("status") == "dry_run_ready" else "invalid"
    if exit_code == 0 and summary.get("exact_match") is True:
        return "pass"
    if exit_code == 2 and summary.get("policy_started_at_unix_s") is not None:
        return "fail"
    return "invalid"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="ascii") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _existing_attempts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]


def pending_schedule_rows(
    rows: list[dict[str, Any]], attempts: list[dict[str, Any]], *, enable_robot: bool
) -> list[dict[str, Any]]:
    if enable_robot:
        completed = {
            attempt["trial_id"]
            for attempt in attempts
            if attempt.get("mode") == "robot" and attempt.get("result") in {"pass", "fail"}
        }
        return [row for row in rows if row["trial_id"] not in completed]
    validated_policies = {
        attempt["policy"]
        for attempt in attempts
        if attempt.get("mode") == "dry_run" and attempt.get("result") == "software_validated"
    }
    remaining = [row for row in rows if row["policy"] not in validated_policies]
    return list({row["policy"]: row for row in remaining}.values())


def scheduled_break_after_row(row: dict[str, Any], protocol: dict[str, Any], *, total_blocks: int) -> bool:
    settings = protocol["scheduled_break"]
    block_index = int(row["block_index"])
    return (
        int(row["order_in_block"]) == len(POLICIES)
        and block_index % int(settings["after_complete_blocks"]) == 0
        and (not bool(settings["exclude_final_block"]) or block_index < total_blocks)
    )


def _run_scheduled_break(session_dir: Path, *, block_index: int, duration_s: float) -> None:
    events_path = session_dir / EVENTS_NAME
    started_at = time.time()
    _append_jsonl(
        events_path,
        {
            "schema_version": 1,
            "kind": "scheduled_break_started",
            "block_index": block_index,
            "duration_s": duration_s,
            "started_at_unix_s": started_at,
        },
    )
    print(f"SCHEDULED BREAK: {duration_s:.0f} s after complete A/B/C block {block_index}.")
    time.sleep(duration_s)
    _append_jsonl(
        events_path,
        {
            "schema_version": 1,
            "kind": "scheduled_break_completed",
            "block_index": block_index,
            "duration_s": duration_s,
            "started_at_unix_s": started_at,
            "completed_at_unix_s": time.time(),
        },
    )


def _session_contract(
    *,
    manifest_path: Path,
    rest_pose: Path,
    device: str,
    port: str,
    robot_id: str,
    enable_robot: bool,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "robot" if enable_robot else "dry_run",
        "benchmark_manifest": str(manifest_path.resolve()),
        "benchmark_manifest_sha256": file_sha256(manifest_path),
        "rest_pose": str(rest_pose.resolve()),
        "rest_pose_sha256": file_sha256(rest_pose),
        "device": device,
        "port": port,
        "robot_id": robot_id,
        "episode_limit_s": protocol["episode_limit_s"],
        "episode_limit_source": protocol["episode_limit_source"],
        "scheduled_break": protocol["scheduled_break"],
    }


def _validate_resume_session(session_dir: Path, expected: dict[str, Any]) -> None:
    actual = _read_json(session_dir / "session.json")
    for field, expected_value in expected.items():
        if actual.get(field) != expected_value:
            raise ValueError(
                f"resume contract mismatch for {field}: expected {expected_value!r}, got {actual.get(field)!r}"
            )


def run_benchmark_session(
    *,
    manifest_path: Path,
    session_dir: Path,
    python: Path,
    rest_pose: Path,
    device: str,
    port: str,
    robot_id: str,
    enable_robot: bool,
    resume: bool,
    max_trials: int | None,
    inter_trial_s: float,
) -> int:
    manifest = load_benchmark_manifest(manifest_path)
    protocol = _read_json(Path(manifest["protocol_path"]))
    rows = read_schedule(Path(manifest["schedule_csv"]))
    scheduled_trial_count = len(rows)
    total_blocks = max(int(row["block_index"]) for row in rows)
    if max_trials is not None and max_trials < 1:
        raise ValueError("max_trials must be positive when provided")
    if inter_trial_s < 0.0:
        raise ValueError("inter_trial_s must be non-negative")

    session_contract = _session_contract(
        manifest_path=manifest_path,
        rest_pose=rest_pose,
        device=device,
        port=port,
        robot_id=robot_id,
        enable_robot=enable_robot,
        protocol=protocol,
    )
    if resume:
        if not session_dir.is_dir():
            raise FileNotFoundError(f"cannot resume missing session: {session_dir}")
        _validate_resume_session(session_dir, session_contract)
    else:
        session_dir.mkdir(parents=True, exist_ok=False)
        session = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            **session_contract,
        }
        (session_dir / "session.json").write_text(
            json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )

    attempts_path = session_dir / ATTEMPTS_NAME
    attempts = _existing_attempts(attempts_path)
    rows = pending_schedule_rows(rows, attempts, enable_robot=enable_robot)
    if max_trials is not None:
        rows = rows[:max_trials]

    for executed, row in enumerate(rows, start=1):
        prior_count = sum(attempt.get("trial_id") == row["trial_id"] for attempt in attempts)
        attempt_index = prior_count + 1
        trial_dir = session_dir / "trials" / row["trial_id"]
        trial_dir.mkdir(parents=True, exist_ok=True)
        runner_log = trial_dir / f"attempt_{attempt_index:03d}.jsonl"
        policy = manifest["policies"][row["policy"]]
        command = build_runner_command(
            python=python,
            policy=policy,
            target=row["sequence"],
            out=runner_log,
            rest_pose=rest_pose,
            device=device,
            port=port,
            robot_id=robot_id,
            enable_robot=enable_robot,
            episode_limit_s=protocol["episode_limit_s"],
        )
        print(f"\n[{row['trial_index']}/{scheduled_trial_count}] {row['trial_id']} {row['sequence']} ({row['policy']})")
        started_at = time.time()
        exit_code = subprocess.run(command, check=False).returncode
        ended_at = time.time()
        runner_summary = read_runner_summary(runner_log)
        result = classify_runner_result(exit_code, runner_summary, dry_run=not enable_robot)
        attempt = {
            "schema_version": 1,
            "kind": "typing_abc_attempt",
            "mode": "robot" if enable_robot else "dry_run",
            **row,
            "attempt_index": attempt_index,
            "result": result,
            "runner_exit_code": exit_code,
            "runner_log": str(runner_log.resolve()),
            "command": command,
            "started_at_unix_s": started_at,
            "ended_at_unix_s": ended_at,
            "runner_summary": runner_summary,
        }
        _append_jsonl(attempts_path, attempt)
        attempts.append(attempt)
        print(f"RESULT: {result}")
        if result == "invalid":
            print("Session stopped: invalid attempts are never scored. Fix the infrastructure and resume.")
            return 1
        if enable_robot and scheduled_break_after_row(row, protocol, total_blocks=total_blocks):
            _run_scheduled_break(
                session_dir,
                block_index=int(row["block_index"]),
                duration_s=float(protocol["scheduled_break"]["duration_s"]),
            )
        if inter_trial_s > 0.0 and executed < len(rows):
            time.sleep(inter_trial_s)
    return 0


def shell_command(command: Iterable[str]) -> str:
    """Render a command only for logs and operator review."""

    import shlex

    return shlex.join(command)


def default_session_dir(root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / timestamp


def default_python() -> Path:
    return Path(sys.executable).resolve()
