# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.so101_homing.typing_ab_timelapse import (
    attempt_video_clip,
    build_attempt_video_command,
    build_triplet_command,
    find_observer_segment,
)


def _segment() -> dict:
    return {
        "video": "/observer.mkv",
        "capture_started_at_unix_s": 100.0,
        "capture_stopped_at_unix_s": 200.0,
    }


def test_attempt_clip_uses_policy_timestamps_not_return_to_rest() -> None:
    attempt = {
        "trial_id": "p001-anchorbench",
        "block_id": "b001",
        "policy": "anchorbench",
        "sequence": "ABCDEF",
        "result": "pass",
        "runner_summary": {
            "policy_started_at_unix_s": 120.0,
            "policy_terminal_at_unix_s": 130.0,
            "completion_time_s": 10.0,
            "stop_reason": "target_complete",
            "wall_duration_s": 15.0,
        },
    }

    clip = attempt_video_clip(attempt, [_segment()], lead_s=0.5, tail_s=1.0)

    assert clip["start_s"] == 19.5
    assert clip["duration_s"] == 11.5
    assert clip["completion_time_s"] == 10.0


def test_observer_segment_must_cover_complete_policy_interval() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        find_observer_segment(
            [_segment()],
            policy_started_at_unix_s=190.0,
            policy_terminal_at_unix_s=210.0,
        )


def test_attempt_video_command_materializes_exact_interval(tmp_path: Path) -> None:
    command = build_attempt_video_command(
        clip={"video": "/observer.mkv", "start_s": 1.25, "duration_s": 7.5},
        output=tmp_path / "episode.mp4",
    )

    assert command[command.index("-ss") + 1] == "1.25"
    assert command[command.index("-t") + 1] == "7.5"
    assert command[command.index("-i") + 1] == "/observer.mkv"
    assert command[-1] == str(tmp_path / "episode.mp4")


def test_triplet_command_places_profiles_in_fixed_column_order(tmp_path: Path) -> None:
    anchor = {
        "video": "/anchor.mkv",
        "start_s": 1.0,
        "duration_s": 12.0,
        "result": "pass",
        "completion_time_s": 10.0,
        "stop_reason": "target_complete",
        "policy": "anchorbench",
        "sequence": "ABCDEF",
    }
    baseline = {
        "video": "/baseline.mkv",
        "start_s": 2.0,
        "duration_s": 15.0,
        "result": "fail",
        "completion_time_s": None,
        "stop_reason": "wrong_key",
        "policy": "baseline",
        "sequence": "ABCDEF",
    }
    usd_drive = {
        "video": "/usd.mkv",
        "start_s": 3.0,
        "duration_s": 13.0,
        "result": "pass",
        "completion_time_s": 11.0,
        "stop_reason": "target_complete",
        "policy": "usd_drive",
        "sequence": "ABCDEF",
    }

    command = build_triplet_command(
        anchor=anchor,
        baseline=baseline,
        usd_drive=usd_drive,
        block_id="b001",
        output=tmp_path / "block.mp4",
        speed=6.0,
    )

    assert command[command.index("-i") + 1] == "/anchor.mkv"
    second_input = command.index("-i", command.index("-i") + 1)
    assert command[second_input + 1] == "/baseline.mkv"
    third_input = command.index("-i", second_input + 1)
    assert command[third_input + 1] == "/usd.mkv"
    filters = command[command.index("-filter_complex") + 1]
    assert "e-" not in filters
    assert "scale=640:360:force_original_aspect_ratio=decrease" in filters
    assert "AnchorBench | PASS | 10.00s" in filters
    assert "Workshop | FAIL | wrong_key" in filters
    assert "USD Drive | PASS | 11.00s" in filters
    assert "b001 | ABCDEF" in filters
    assert command[command.index("-r") + 1] == "30"
