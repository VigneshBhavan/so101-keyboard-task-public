# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Freeze matched AnchorBench, Workshop, and USD checkpoints into a manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from .typing_ab_execution import finalize_benchmark_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-dir", type=Path, required=True)
    parser.add_argument("--anchor-checkpoint", type=Path, required=True)
    parser.add_argument("--anchor-env-config", type=Path, required=True)
    parser.add_argument("--baseline-checkpoint", type=Path, required=True)
    parser.add_argument("--baseline-env-config", type=Path, required=True)
    parser.add_argument("--usd-drive-checkpoint", type=Path, required=True)
    parser.add_argument("--usd-drive-env-config", type=Path, required=True)
    parser.add_argument("--stage", default="p1d")
    parser.add_argument("--task-profile", default="physical-calibrated-20260718")
    args = parser.parse_args()

    output = finalize_benchmark_manifest(
        args.protocol_dir.resolve(),
        anchor_checkpoint=args.anchor_checkpoint.resolve(),
        anchor_env_config=args.anchor_env_config.resolve(),
        baseline_checkpoint=args.baseline_checkpoint.resolve(),
        baseline_env_config=args.baseline_env_config.resolve(),
        usd_drive_checkpoint=args.usd_drive_checkpoint.resolve(),
        usd_drive_env_config=args.usd_drive_env_config.resolve(),
        stage=args.stage,
        task_profile=args.task_profile,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
