# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Stage a physical A/B/C typing benchmark for review before Hugging Face upload."""

from __future__ import annotations

import argparse
from pathlib import Path

from .typing_ab_release import prepare_release_folder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--timelapse", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--include-runner-logs", action="store_true")
    args = parser.parse_args()

    output = prepare_release_folder(
        session_dir=args.session_dir.resolve(),
        timelapse=args.timelapse.resolve(),
        output_dir=args.out.resolve(),
        allow_partial=args.allow_partial,
        include_runner_logs=args.include_runner_logs,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
