# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Build matched observer-video timelapses from physical typing A/B/C attempts."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .typing_ab_benchmark import POLICIES
from .typing_ab_results import scored_attempts, write_session_summary

FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
POLICY_LABEL = {"anchorbench": "AnchorBench", "baseline": "Workshop", "usd_drive": "USD Drive"}


def load_observer_segments(session_dir: Path) -> list[dict[str, Any]]:
    path = session_dir / "observer_segments.jsonl"
    if not path.is_file():
        raise FileNotFoundError(path)
    values = [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    for value in values:
        video = Path(value["video"])
        if not video.is_file():
            raise FileNotFoundError(video)
    return values


def find_observer_segment(
    segments: list[dict[str, Any]],
    *,
    policy_started_at_unix_s: float,
    policy_terminal_at_unix_s: float,
) -> dict[str, Any]:
    matches = [
        segment
        for segment in segments
        if float(segment["capture_started_at_unix_s"]) <= policy_started_at_unix_s
        and float(segment["capture_stopped_at_unix_s"]) >= policy_terminal_at_unix_s
    ]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one observer segment covering policy interval "
            f"[{policy_started_at_unix_s}, {policy_terminal_at_unix_s}], found {len(matches)}"
        )
    return matches[0]


def attempt_video_clip(
    attempt: dict[str, Any],
    segments: list[dict[str, Any]],
    *,
    lead_s: float,
    tail_s: float,
) -> dict[str, Any]:
    summary = attempt["runner_summary"]
    policy_start = float(summary["policy_started_at_unix_s"])
    policy_terminal = float(summary["policy_terminal_at_unix_s"])
    segment = find_observer_segment(
        segments,
        policy_started_at_unix_s=policy_start,
        policy_terminal_at_unix_s=policy_terminal,
    )
    capture_start = float(segment["capture_started_at_unix_s"])
    capture_stop = float(segment["capture_stopped_at_unix_s"])
    start_s = max(0.0, policy_start - capture_start - lead_s)
    desired_end_s = policy_terminal - capture_start + tail_s
    end_s = min(capture_stop - capture_start, desired_end_s)
    if end_s <= start_s:
        raise ValueError(f"invalid observer clip interval for {attempt['trial_id']}")
    return {
        "trial_id": attempt["trial_id"],
        "policy": attempt["policy"],
        "sequence": attempt["sequence"],
        "result": attempt["result"],
        "completion_time_s": summary.get("completion_time_s"),
        "stop_reason": summary.get("stop_reason"),
        "video": segment["video"],
        "start_s": start_s,
        "duration_s": end_s - start_s,
    }


def _drawtext_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _attempt_label(clip: dict[str, Any]) -> str:
    label = POLICY_LABEL[clip["policy"]]
    if clip["result"] == "pass":
        timing = f"{float(clip['completion_time_s']):.2f}s"
        return f"{label} | PASS | {timing}"
    return f"{label} | FAIL | {clip['stop_reason'] or 'unknown'}"


def build_attempt_video_command(*, clip: dict[str, Any], output: Path) -> list[str]:
    """Materialize one scored policy interval as a standalone MP4."""

    return [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{clip['start_s']:.9g}",
        "-t",
        f"{clip['duration_s']:.9g}",
        "-i",
        clip["video"],
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-movflags",
        "+faststart",
        str(output),
    ]


def materialize_attempt_video(clip: dict[str, Any], *, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        subprocess.run(build_attempt_video_command(clip=clip, output=output), check=True)
    subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_streams", str(output)],
        check=True,
        capture_output=True,
    )
    materialized = dict(clip)
    materialized["source_video"] = clip["video"]
    materialized["source_start_s"] = clip["start_s"]
    materialized["video"] = str(output.resolve())
    materialized["start_s"] = 0.0
    materialized["episode_video"] = str(output.resolve())
    return materialized


def build_triplet_command(
    *,
    anchor: dict[str, Any],
    baseline: dict[str, Any],
    usd_drive: dict[str, Any],
    block_id: str,
    output: Path,
    speed: float,
) -> list[str]:
    if speed <= 0.0:
        raise ValueError("timelapse speed must be positive")
    clips = (anchor, baseline, usd_drive)
    target_duration = max(clip["duration_s"] / speed for clip in clips)
    title = _drawtext_escape(f"{block_id} | {anchor['sequence']}")
    font = str(FONT)
    streams = []
    for index, clip in enumerate(clips):
        pad = max(0.0, target_duration - clip["duration_s"] / speed)
        if pad < 1.0e-6:
            pad = 0.0
        label = _drawtext_escape(_attempt_label(clip))
        streams.append(
            f"[{index}:v]setpts=(PTS-STARTPTS)/{speed:.9g},"
            "scale=640:360:force_original_aspect_ratio=decrease,"
            "pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,"
            f"tpad=stop_mode=clone:stop_duration={pad:.9g},"
            "drawbox=x=0:y=0:w=iw:h=38:color=black@0.72:t=fill,"
            f"drawtext=fontfile={font}:text='{label}':x=12:y=9:fontsize=18:fontcolor=white[v{index}]"
        )
    filters = (
        ";".join(streams)
        + ";[v0][v1][v2]hstack=inputs=3,"
        f"drawbox=x=0:y=h-42:w=iw:h=42:color=black@0.72:t=fill,"
        f"drawtext=fontfile={font}:text='{title}':x=(w-text_w)/2:y=h-32:fontsize=22:fontcolor=white[out]"
    )
    command = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    for clip in clips:
        command.extend(
            (
                "-ss",
                f"{clip['start_s']:.9g}",
                "-t",
                f"{clip['duration_s']:.9g}",
                "-i",
                clip["video"],
            )
        )
    command.extend(
        [
        "-filter_complex",
        filters,
        "-map",
        "[out]",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        str(output),
        ]
    )
    return command


def build_timelapse(
    session_dir: Path,
    *,
    output: Path,
    speed: float = 6.0,
    lead_s: float = 0.5,
    tail_s: float = 1.0,
    max_blocks: int | None = None,
    keep_temp: bool = False,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    if max_blocks is not None and max_blocks < 1:
        raise ValueError("max_blocks must be positive when provided")
    attempts = scored_attempts(session_dir)
    segments = load_observer_segments(session_dir)
    blocks: dict[str, dict[str, dict[str, Any]]] = {}
    for attempt in attempts.values():
        clip = attempt_video_clip(attempt, segments, lead_s=lead_s, tail_s=tail_s)
        blocks.setdefault(attempt["block_id"], {})[attempt["policy"]] = clip
    complete = [(block_id, block) for block_id, block in sorted(blocks.items()) if set(block) == set(POLICIES)]
    if max_blocks is not None:
        complete = complete[:max_blocks]
    if not complete:
        raise ValueError("no complete scored/video-covered A/B/C blocks are available")

    output.parent.mkdir(parents=True, exist_ok=True)
    episode_dir = session_dir / "episode_videos"
    temp_dir = Path(tempfile.mkdtemp(prefix="typing_ab_timelapse_", dir=output.parent))
    metadata_blocks = []
    try:
        segment_paths = []
        for index, (block_id, block) in enumerate(complete, start=1):
            block = {
                policy: materialize_attempt_video(
                    clip,
                    output=episode_dir / f"{clip['trial_id']}.mp4",
                )
                for policy, clip in block.items()
            }
            segment_path = temp_dir / f"block_{index:03d}.mp4"
            command = build_triplet_command(
                anchor=block["anchorbench"],
                baseline=block["baseline"],
                usd_drive=block["usd_drive"],
                block_id=block_id,
                output=segment_path,
                speed=speed,
            )
            subprocess.run(command, check=True)
            segment_paths.append(segment_path)
            metadata_blocks.append(
                {
                    "block_id": block_id,
                    "sequence": block["anchorbench"]["sequence"],
                    "anchorbench": block["anchorbench"],
                    "baseline": block["baseline"],
                    "usd_drive": block["usd_drive"],
                }
            )
        concat_path = temp_dir / "concat.txt"
        concat_lines = []
        for path in segment_paths:
            escaped = str(path).replace("'", "'\\''")
            concat_lines.append(f"file '{escaped}'\n")
        concat_path.write_text(
            "".join(concat_lines),
            encoding="utf-8",
        )
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )
        subprocess.run(
            [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_streams", str(output)],
            check=True,
            capture_output=True,
        )
        write_session_summary(session_dir)
        metadata = {
            "schema_version": 1,
            "session_dir": str(session_dir.resolve()),
            "output": str(output.resolve()),
            "speed": speed,
            "lead_s": lead_s,
            "tail_s": tail_s,
            "block_count": len(metadata_blocks),
            "episode_video_dir": str(episode_dir.resolve()),
            "episode_video_count": len(metadata_blocks) * len(POLICIES),
            "blocks": metadata_blocks,
        }
        metadata_path = output.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="ascii")
        metadata["metadata_path"] = str(metadata_path.resolve())
        return metadata
    finally:
        if not keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
