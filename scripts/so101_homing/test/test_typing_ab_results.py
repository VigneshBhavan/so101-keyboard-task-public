# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.so101_homing.typing_ab_benchmark import prepare_protocol_bundle
from scripts.so101_homing.typing_ab_release import prepare_release_folder
from scripts.so101_homing.typing_ab_results import (
    exact_mcnemar_p_value,
    summarize_session,
    timing_summary,
    wilson_interval,
    write_session_summary,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="ascii")


def _session(tmp_path: Path) -> Path:
    protocol = prepare_protocol_bundle(tmp_path / "protocol", count=2, seed=5)
    manifest = {
        "schedule_csv": str(protocol["schedule_csv"]),
        "protocol_path": str(protocol["protocol"]),
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="ascii")
    session = tmp_path / "session"
    session.mkdir()
    (session / "session.json").write_text(json.dumps({"benchmark_manifest": str(manifest_path)}), encoding="ascii")
    with protocol["schedule_csv"].open(newline="", encoding="ascii") as handle:
        schedule = list(csv.DictReader(handle))
    attempts = []
    results = (
        (schedule[0], "pass", 2.0, "target_complete"),
        (schedule[1], "fail", None, "wrong_key"),
        (schedule[2], "pass", 2.5, "target_complete"),
        (schedule[3], "pass", 4.0, "target_complete"),
        (schedule[4], "fail", None, "wrong_key"),
        (schedule[5], "pass", 3.0, "target_complete"),
    )
    for row, result, completion_time_s, stop_reason in results:
        attempts.append(
            {
                **row,
                "mode": "robot",
                "result": result,
                "runner_log": f"/{row['trial_id']}.jsonl",
                "runner_summary": {
                    "completion_time_s": completion_time_s,
                    "stop_reason": stop_reason,
                },
            }
        )
    _write_jsonl(session / "attempts.jsonl", attempts)
    _write_jsonl(
        session / "observer_segments.jsonl",
        [{"video": "/source/observer.mkv", "capture_started_at_unix_s": 1.0}],
    )
    return session


def test_wilson_and_exact_mcnemar_statistics() -> None:
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=0.001)
    assert high == pytest.approx(0.5962, abs=0.001)
    assert exact_mcnemar_p_value(5, 0) == pytest.approx(0.0625)
    assert exact_mcnemar_p_value(0, 0) == 1.0


def test_timing_summary_handles_single_and_empty_samples() -> None:
    assert timing_summary([])["mean_s"] is None
    values = timing_summary([2.0])
    assert values["mean_s"] == 2.0
    assert values["std_s"] == 0.0


def test_session_summary_is_paired_and_excludes_failed_timing(tmp_path: Path) -> None:
    session = _session(tmp_path)

    summary, rows = summarize_session(session)

    assert len(rows) == 6
    assert summary["benchmark_complete"] is True
    assert summary["policy"]["anchorbench"]["strict_successes"] == 2
    assert summary["policy"]["baseline"]["strict_successes"] == 1
    assert summary["policy"]["usd_drive"]["strict_successes"] == 1
    assert summary["policy"]["baseline"]["successful_completion_time"]["count"] == 1
    assert summary["matched"]["complete_blocks"] == 2
    assert summary["matched"]["exactly_two_pass"] == 2
    anchor_vs_baseline = summary["matched"]["pairwise"]["anchorbench_vs_baseline"]
    assert anchor_vs_baseline["both_pass"] == 1
    assert anchor_vs_baseline["first_only_pass"] == 1
    assert anchor_vs_baseline["second_only_pass"] == 0
    assert anchor_vs_baseline["completion_time_delta_first_minus_second_s"]["mean_s"] == -1.0
    failed = next(row for row in rows if row["result"] == "fail")
    assert failed["completion_time_s"] is None


def test_summary_writer_produces_json_csv_and_markdown(tmp_path: Path) -> None:
    session = _session(tmp_path)

    paths = write_session_summary(session)

    assert all(path.is_file() for path in paths.values())
    assert "2/2 strict success" in paths["markdown"].read_text()


def test_release_package_is_create_once_and_hashes_review_artifacts(tmp_path: Path) -> None:
    session = _session(tmp_path)
    timelapse = tmp_path / "typing_ab.mp4"
    timelapse.write_bytes(b"synthetic video")
    timelapse.with_suffix(".json").write_text("{}\n", encoding="ascii")
    output = tmp_path / "release"

    prepare_release_folder(session_dir=session, timelapse=timelapse, output_dir=output)

    manifest = json.loads((output / "release_manifest.json").read_text())
    paths = {artifact["path"] for artifact in manifest["artifacts"]}
    assert "benchmark/corpus.json" in paths
    assert "results/summary/summary.json" in paths
    assert "media/typing_ab.mp4" in paths
    with pytest.raises(FileExistsError):
        prepare_release_folder(session_dir=session, timelapse=timelapse, output_dir=output)
