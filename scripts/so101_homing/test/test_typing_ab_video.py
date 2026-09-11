# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.so101_homing.typing_ab_video import (
    _supports_observer_stream,
    append_observer_segment,
    build_capture_command,
)


def test_capture_command_uses_logitech_c920_stream_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.so101_homing.typing_ab_video.shutil.which", lambda name: f"/usr/bin/{name}")
    output = tmp_path / "observer.mkv"
    command = build_capture_command(device=Path("/dev/video8"), output=output, fps=30)

    assert command[command.index("-input_format") + 1] == "mjpeg"
    assert command[command.index("-video_size") + 1] == "1280x720"
    assert command[command.index("-framerate") + 1] == "30"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[-1] == str(output)


def test_required_stream_parser_keeps_size_and_rate_within_mjpg_block() -> None:
    valid = """
        [0]: 'YUYV' (YUYV 4:2:2)
            Size: Discrete 1280x720
                Interval: Discrete 0.100s (10.000 fps)
        [1]: 'MJPG' (Motion-JPEG, compressed)
            Size: Discrete 1280x720
                Interval: Discrete 0.033s (30.000 fps)
    """
    wrong_format = valid.replace("[1]: 'MJPG'", "[1]: 'YUYV'")
    wrong_size = valid.replace("Size: Discrete 1280x720", "Size: Discrete 640x480")

    assert _supports_observer_stream(valid)
    assert not _supports_observer_stream(wrong_format)
    assert not _supports_observer_stream(wrong_size)


def test_capture_command_rejects_invalid_fps(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fps"):
        build_capture_command(
            device=Path("/dev/video8"),
            output=tmp_path / "observer.mkv",
            fps=0,
        )


def test_observer_segments_are_append_only(tmp_path: Path) -> None:
    append_observer_segment(tmp_path, {"video": "/first.mkv"})
    append_observer_segment(tmp_path, {"video": "/second.mkv"})

    rows = [json.loads(line) for line in (tmp_path / "observer_segments.jsonl").read_text().splitlines()]
    assert rows == [{"video": "/first.mkv"}, {"video": "/second.mkv"}]
