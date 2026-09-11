# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Logitech C920 observer capture for physical typing benchmark sessions."""

from __future__ import annotations

import json
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

OBSERVER_CAMERA_NAME = "HD Pro Webcam C920"
OBSERVER_DEVICE_GLOB = "usb-046d_HD_Pro_Webcam_C920_*-video-index0"
OBSERVER_INPUT_FORMAT = "mjpeg"
OBSERVER_PIXEL_FORMAT = "MJPG"
OBSERVER_VIDEO_SIZE = "1280x720"
OBSERVER_WIDTH = 1280
OBSERVER_HEIGHT = 720
OBSERVER_FPS = 30


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required observer-video tool is not installed: {name}")
    return path


def _camera_name(device: Path) -> str:
    path = Path("/sys/class/video4linux") / device.resolve().name / "name"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _formats(device: Path) -> str:
    result = subprocess.run(
        [_require_tool("v4l2-ctl"), "-d", str(device), "--list-formats-ext"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def _supports_observer_stream(formats: str) -> bool:
    active_format = ""
    active_size = ""
    for line in formats.splitlines():
        format_match = re.search(r"\[\d+\]: '([^']+)'", line)
        if format_match:
            active_format = format_match.group(1)
            active_size = ""
            continue
        size_match = re.search(r"Size: Discrete (\d+x\d+)", line)
        if size_match:
            active_size = size_match.group(1)
            continue
        if active_format == OBSERVER_PIXEL_FORMAT and active_size == OBSERVER_VIDEO_SIZE and "(30.000 fps)" in line:
            return True
    return False


def _validate_observer_camera(device: Path) -> None:
    if not device.is_char_device():
        raise FileNotFoundError(f"observer camera is not a video device: {device}")
    name = _camera_name(device)
    if name != OBSERVER_CAMERA_NAME:
        raise RuntimeError(f"{device} is {name!r}, expected {OBSERVER_CAMERA_NAME!r}")
    formats = _formats(device)
    if not _supports_observer_stream(formats):
        raise RuntimeError(
            f"{device} does not expose the required {OBSERVER_PIXEL_FORMAT} "
            f"{OBSERVER_VIDEO_SIZE} at {OBSERVER_FPS} fps stream"
        )


def resolve_observer_device(value: str) -> Path:
    if value != "auto":
        device = Path(value).absolute()
        _validate_observer_camera(device)
        return device
    matches: list[Path] = []
    for device in sorted(Path("/dev/v4l/by-id").glob(OBSERVER_DEVICE_GLOB)):
        try:
            _validate_observer_camera(device)
        except (FileNotFoundError, RuntimeError):
            continue
        matches.append(device)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one stable {OBSERVER_CAMERA_NAME} capture node matching "
            f"/dev/v4l/by-id/{OBSERVER_DEVICE_GLOB}; "
            f"found {len(matches)}: {[str(path) for path in matches]}"
        )
    return matches[0]


def _usb_root_bus(device: Path) -> str | None:
    result = subprocess.run(
        [_require_tool("udevadm"), "info", "-q", "path", "-n", str(device)],
        check=False,
        capture_output=True,
        text=True,
    )
    for component in result.stdout.split("/"):
        if component.startswith("usb") and component[3:].isdigit():
            return component
    return None


def build_capture_command(*, device: Path, output: Path, fps: int) -> list[str]:
    if fps < 1:
        raise ValueError("observer fps must be positive")
    return [
        _require_tool("ffmpeg"),
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "v4l2",
        "-input_format",
        OBSERVER_INPUT_FORMAT,
        "-video_size",
        OBSERVER_VIDEO_SIZE,
        "-framerate",
        str(fps),
        "-i",
        str(device),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-g",
        str(2 * fps),
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]


def _probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            _require_tool("ffprobe"),
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration:stream=width,height,avg_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not payload.get("streams"):
        raise RuntimeError(f"observer capture has no video stream: {path}")
    return payload


@dataclass
class ObserverCapture:
    device: Path
    output_dir: Path
    fps: int = OBSERVER_FPS
    warmup_s: float = 4.0
    process: subprocess.Popen | None = field(default=None, init=False)
    metadata: dict[str, Any] | None = field(default=None, init=False)
    _log_handle: TextIO | None = field(default=None, init=False)

    def start(self) -> ObserverCapture:
        if self.process is not None:
            raise RuntimeError("observer capture is already running")
        _validate_observer_camera(self.device)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video = self.output_dir / f"observer_{timestamp}.mkv"
        log = self.output_dir / f"observer_{timestamp}_ffmpeg.log"
        metadata_path = self.output_dir / f"observer_{timestamp}.json"
        command = build_capture_command(device=self.device, output=video, fps=self.fps)
        self._log_handle = log.open("w", encoding="utf-8")
        started_at = time.time()
        self.process = subprocess.Popen(
            command,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
        )
        time.sleep(self.warmup_s)
        if self.process.poll() is not None:
            self._log_handle.close()
            self._log_handle = None
            raise RuntimeError(f"observer capture exited during warmup; inspect {log}")
        self.metadata = {
            "schema_version": 1,
            "kind": "typing_ab_observer_segment",
            "device": str(self.device),
            "resolved_device": str(self.device.resolve()),
            "camera_name": _camera_name(self.device),
            "camera_profile": "logitech_c920_mjpeg_1280x720_30fps",
            "usb_root_bus": _usb_root_bus(self.device),
            "fps": self.fps,
            "input_format": OBSERVER_INPUT_FORMAT,
            "width": OBSERVER_WIDTH,
            "height": OBSERVER_HEIGHT,
            "video": str(video.resolve()),
            "ffmpeg_log": str(log.resolve()),
            "metadata_path": str(metadata_path.resolve()),
            "capture_started_at_unix_s": started_at,
            "benchmark_ready_at_unix_s": time.time(),
            "ffmpeg_command": command,
        }
        print(f"Observer recording: {video}")
        return self

    def assert_running(self) -> None:
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("observer capture is not running")

    def stop(self) -> dict[str, Any]:
        if self.process is None or self.metadata is None:
            raise RuntimeError("observer capture was not started")
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=15.0)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5.0)
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
        self.metadata["capture_stopped_at_unix_s"] = time.time()
        self.metadata["ffmpeg_exit_code"] = self.process.returncode
        video = Path(self.metadata["video"])
        if self.process.returncode not in (0, 255) or not video.is_file() or video.stat().st_size == 0:
            raise RuntimeError(
                f"observer capture failed with exit {self.process.returncode}; inspect {self.metadata['ffmpeg_log']}"
            )
        self.metadata["probe"] = _probe_video(video)
        metadata_path = Path(self.metadata["metadata_path"])
        metadata_path.write_text(
            json.dumps(self.metadata, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        return self.metadata

    def __enter__(self) -> ObserverCapture:
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()


def append_observer_segment(session_dir: Path, metadata: dict[str, Any]) -> None:
    path = session_dir / "observer_segments.jsonl"
    with path.open("a", encoding="ascii") as handle:
        handle.write(json.dumps(metadata, sort_keys=True) + "\n")


def preflight_report(device: Path) -> dict[str, Any]:
    _validate_observer_camera(device)
    return {
        "device": str(device),
        "resolved_device": str(device.resolve()),
        "camera_name": _camera_name(device),
        "camera_profile": "logitech_c920_mjpeg_1280x720_30fps",
        "usb_root_bus": _usb_root_bus(device),
        "required_stream": f"{OBSERVER_PIXEL_FORMAT} {OBSERVER_VIDEO_SIZE} at {OBSERVER_FPS} fps",
        "ffmpeg": _require_tool("ffmpeg"),
        "ffprobe": _require_tool("ffprobe"),
        "v4l2_ctl": _require_tool("v4l2-ctl"),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
