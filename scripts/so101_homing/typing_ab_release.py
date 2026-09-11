# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Create a reviewable release folder for one physical typing A/B/C session."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .typing_ab_benchmark import file_sha256
from .typing_ab_results import write_session_summary


def _copy(source: Path, destination: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _artifact_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "release_manifest.json"
    ]


def prepare_release_folder(
    *,
    session_dir: Path,
    timelapse: Path,
    output_dir: Path,
    allow_partial: bool = False,
    include_runner_logs: bool = False,
) -> Path:
    if output_dir.exists():
        raise FileExistsError(f"refusing to replace release folder: {output_dir}")
    summary_paths = write_session_summary(session_dir)
    summary = json.loads(summary_paths["json"].read_text(encoding="ascii"))
    if not summary["benchmark_complete"] and not allow_partial:
        raise ValueError("benchmark is incomplete; use --allow-partial only for an internal review package")
    session = json.loads((session_dir / "session.json").read_text(encoding="ascii"))
    benchmark_manifest = Path(session["benchmark_manifest"])
    manifest = json.loads(benchmark_manifest.read_text(encoding="ascii"))
    protocol = Path(manifest["protocol_path"])
    protocol_dir = protocol.parent
    timelapse_metadata = timelapse.with_suffix(".json")

    output_dir.mkdir(parents=True, exist_ok=False)
    _copy(benchmark_manifest, output_dir / "benchmark/benchmark_manifest.json")
    for name in ("protocol.json", "corpus.json", "schedule.json", "schedule.csv"):
        _copy(protocol_dir / name, output_dir / f"benchmark/{name}")
    for name in ("session.json", "attempts.jsonl", "observer_segments.jsonl"):
        _copy(session_dir / name, output_dir / f"results/{name}")
    for source in summary_paths.values():
        _copy(source, output_dir / f"results/summary/{source.name}")
    _copy(timelapse, output_dir / f"media/{timelapse.name}")
    _copy(timelapse_metadata, output_dir / f"media/{timelapse_metadata.name}")
    if include_runner_logs:
        shutil.copytree(session_dir / "trials", output_dir / "results/trials")

    readme = "\n".join(
        (
            "# SO-101 Physical Typing A/B/C",
            "",
            "This folder contains the frozen matched corpus, exact checkpoint/environment ",
            "manifests, scored attempt ledger, statistics, and three-profile observer timelapse.",
            "",
            f"Benchmark complete: {summary['benchmark_complete']}",
            f"Scored attempts: {summary['scored_trials']}/{summary['schedule_trials']}",
            "",
            "Completion time excludes reset and return-to-rest. Failed attempts are incomplete.",
            "Raw observer segments are retained in the source session and are not duplicated here.",
            "",
        )
    )
    (output_dir / "README.md").write_text(readme, encoding="ascii")
    release_manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_session": str(session_dir.resolve()),
        "benchmark_complete": summary["benchmark_complete"],
        "runner_logs_included": include_runner_logs,
        "artifacts": _artifact_rows(output_dir),
    }
    (output_dir / "release_manifest.json").write_text(
        json.dumps(release_manifest, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return output_dir
