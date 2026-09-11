# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Prepare immutable inputs for the physical SO-101 typing A/B/C benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

from .typing_ab_benchmark import prepare_protocol_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--sequence-length", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument(
        "--episode-limit-s",
        type=float,
        default=None,
        help="Optional external cutoff. Omit to use each checkpoint's native stage contract.",
    )
    parser.add_argument("--break-every-blocks", type=int, default=20)
    parser.add_argument("--break-duration-s", type=float, default=60.0)
    args = parser.parse_args()

    paths = prepare_protocol_bundle(
        args.out.resolve(),
        count=args.count,
        sequence_length=args.sequence_length,
        seed=args.seed,
        episode_limit_s=args.episode_limit_s,
        break_every_blocks=args.break_every_blocks,
        break_duration_s=args.break_duration_s,
    )
    for label, path in paths.items():
        print(f"{label}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
