# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Statistical summaries for matched physical typing benchmark sessions."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import Any

from .typing_ab_benchmark import POLICIES
from .typing_ab_execution import ATTEMPTS_NAME

SCORED_RESULTS = {"pass", "fail"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]


def scored_attempts(session_dir: Path) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for attempt in _read_jsonl(session_dir / ATTEMPTS_NAME):
        if attempt.get("mode") != "robot" or attempt.get("result") not in SCORED_RESULTS:
            continue
        trial_id = attempt["trial_id"]
        if trial_id in selected:
            raise ValueError(f"multiple scored attempts exist for {trial_id}")
        selected[trial_id] = attempt
    return selected


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if total < 1 or not 0 <= successes <= total:
        raise ValueError("Wilson interval requires 0 <= successes <= positive total")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total**2))
    margin /= denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def timing_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    samples = [float(value) for value in values]
    if not samples:
        return {
            "count": 0,
            "mean_s": None,
            "median_s": None,
            "std_s": None,
            "q1_s": None,
            "q3_s": None,
            "min_s": None,
            "max_s": None,
        }
    return {
        "count": len(samples),
        "mean_s": statistics.mean(samples),
        "median_s": statistics.median(samples),
        "std_s": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "q1_s": _quantile(samples, 0.25),
        "q3_s": _quantile(samples, 0.75),
        "min_s": min(samples),
        "max_s": max(samples),
    }


def exact_mcnemar_p_value(first_only: int, second_only: int) -> float:
    discordant = first_only + second_only
    if discordant == 0:
        return 1.0
    smaller = min(first_only, second_only)
    lower_tail = sum(math.comb(discordant, value) for value in range(smaller + 1)) / 2**discordant
    return min(1.0, 2.0 * lower_tail)


def _completion_time(attempt: dict[str, Any]) -> float | None:
    if attempt["result"] != "pass":
        return None
    value = attempt.get("runner_summary", {}).get("completion_time_s")
    if value is None or float(value) <= 0.0:
        raise ValueError(f"successful trial {attempt['trial_id']} has no valid completion_time_s")
    return float(value)


def summarize_session(session_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    session = json.loads((session_dir / "session.json").read_text(encoding="ascii"))
    manifest = json.loads(Path(session["benchmark_manifest"]).read_text(encoding="ascii"))
    with Path(manifest["schedule_csv"]).open(newline="", encoding="ascii") as handle:
        schedule = list(csv.DictReader(handle))
    attempts = scored_attempts(session_dir)
    trial_rows: list[dict[str, Any]] = []
    by_block: dict[str, dict[str, dict[str, Any]]] = {}
    for scheduled in schedule:
        attempt = attempts.get(scheduled["trial_id"])
        row = {
            **scheduled,
            "scored": attempt is not None,
            "result": attempt["result"] if attempt is not None else "pending",
            "completion_time_s": _completion_time(attempt) if attempt is not None else None,
            "stop_reason": (attempt.get("runner_summary", {}).get("stop_reason") if attempt is not None else None),
            "runner_log": attempt.get("runner_log") if attempt is not None else None,
        }
        trial_rows.append(row)
        if attempt is not None:
            by_block.setdefault(scheduled["block_id"], {})[scheduled["policy"]] = row

    policy_summary: dict[str, Any] = {}
    for policy in POLICIES:
        rows = [row for row in trial_rows if row["policy"] == policy and row["scored"]]
        successes = sum(row["result"] == "pass" for row in rows)
        interval = wilson_interval(successes, len(rows)) if rows else (None, None)
        completion_times = [row["completion_time_s"] for row in rows if row["completion_time_s"] is not None]
        policy_summary[policy] = {
            "scored_trials": len(rows),
            "strict_successes": successes,
            "strict_failures": len(rows) - successes,
            "strict_success_rate": successes / len(rows) if rows else None,
            "strict_success_wilson95": {"low": interval[0], "high": interval[1]},
            "successful_completion_time": timing_summary(completion_times),
            "failure_reasons": dict(
                Counter(row["stop_reason"] or "unknown" for row in rows if row["result"] == "fail")
            ),
        }

    complete_blocks = [block for block in by_block.values() if set(block) == set(POLICIES)]
    pairwise: dict[str, Any] = {}
    for first, second in combinations(POLICIES, 2):
        complete = [block for block in by_block.values() if {first, second}.issubset(block)]
        both_pass = sum(block[first]["result"] == block[second]["result"] == "pass" for block in complete)
        first_only = sum(
            block[first]["result"] == "pass" and block[second]["result"] == "fail" for block in complete
        )
        second_only = sum(
            block[first]["result"] == "fail" and block[second]["result"] == "pass" for block in complete
        )
        both_fail = len(complete) - both_pass - first_only - second_only
        timing_deltas = [
            block[first]["completion_time_s"] - block[second]["completion_time_s"]
            for block in complete
            if block[first]["result"] == block[second]["result"] == "pass"
        ]
        pairwise[f"{first}_vs_{second}"] = {
            "first_policy": first,
            "second_policy": second,
            "complete_blocks": len(complete),
            "both_pass": both_pass,
            "first_only_pass": first_only,
            "second_only_pass": second_only,
            "both_fail": both_fail,
            "exact_mcnemar_p_value": exact_mcnemar_p_value(first_only, second_only),
            "completion_time_delta_first_minus_second_s": timing_summary(timing_deltas),
        }

    pass_count_distribution = Counter(
        sum(block[policy]["result"] == "pass" for policy in POLICIES) for block in complete_blocks
    )
    summary = {
        "schema_version": 1,
        "session_dir": str(session_dir.resolve()),
        "benchmark_manifest": session["benchmark_manifest"],
        "schedule_trials": len(schedule),
        "scored_trials": len(attempts),
        "benchmark_complete": len(attempts) == len(schedule),
        "policy": policy_summary,
        "matched": {
            "complete_blocks": len(complete_blocks),
            "all_pass": pass_count_distribution[3],
            "exactly_two_pass": pass_count_distribution[2],
            "exactly_one_pass": pass_count_distribution[1],
            "all_fail": pass_count_distribution[0],
            "pairwise": pairwise,
        },
        "timing_contract": (
            "completion_time_s is policy handoff to final matching release and required clearance; "
            "return-to-rest is excluded and failed trials have no completion time"
        ),
    }
    return summary, trial_rows


def write_session_summary(session_dir: Path, output_dir: Path | None = None) -> dict[str, Path]:
    summary, rows = summarize_session(session_dir)
    destination = output_dir or session_dir / "summary"
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "summary.json"
    csv_path = destination / "trials.csv"
    markdown_path = destination / "summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    with csv_path.open("w", newline="", encoding="ascii") as handle:
        fieldnames = list(rows[0]) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# SO-101 Typing Physical A/B/C", ""]
    for policy in POLICIES:
        values = summary["policy"][policy]
        rate = values["strict_success_rate"]
        rate_text = "pending" if rate is None else f"{100.0 * rate:.1f}%"
        lines.append(f"- {policy}: {values['strict_successes']}/{values['scored_trials']} strict success ({rate_text})")
    matched = summary["matched"]
    lines.extend(("", f"Complete A/B/C word blocks: {matched['complete_blocks']}/100"))
    for name, comparison in matched["pairwise"].items():
        lines.append(f"- {name} exact McNemar p-value: {comparison['exact_mcnemar_p_value']:.6g}")
    lines.extend(("", summary["timing_contract"], ""))
    markdown_path.write_text("\n".join(lines), encoding="ascii")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path}
