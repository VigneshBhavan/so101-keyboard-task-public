# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Build a three-profile observer timelapse for a physical typing A/B/C session."""

from __future__ import annotations

import argparse
from pathlib import Path

from .typing_ab_timelapse import build_timelapse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--speed", type=float, default=6.0)
    parser.add_argument("--lead-s", type=float, default=0.5)
    parser.add_argument("--tail-s", type=float, default=1.0)
    parser.add_argument("--max-blocks", "--max-pairs", dest="max_blocks", type=int, default=None)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    metadata = build_timelapse(
        args.session_dir.resolve(),
        output=args.out.resolve(),
        speed=args.speed,
        lead_s=args.lead_s,
        tail_s=args.tail_s,
        max_blocks=args.max_blocks,
        keep_temp=args.keep_temp,
    )
    print(metadata["output"])
    print(metadata["metadata_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
