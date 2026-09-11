# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Validate the Logitech C920 observer path before a physical typing benchmark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .typing_ab_video import ObserverCapture, preflight_report, resolve_observer_device


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--record-test-dir", type=Path, default=None)
    parser.add_argument("--record-test-s", type=float, default=3.0)
    args = parser.parse_args()

    device = resolve_observer_device(args.device)
    report = preflight_report(device)
    if args.record_test_dir is not None:
        with ObserverCapture(device=device, output_dir=args.record_test_dir.resolve()) as capture:
            capture.assert_running()
            time.sleep(args.record_test_s)
        report["record_test"] = capture.metadata
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
