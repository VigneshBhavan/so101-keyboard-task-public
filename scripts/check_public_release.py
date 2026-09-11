#!/usr/bin/env python3
"""Reject infrastructure-specific files, machine paths and credential material."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'cluster integration': re.compile(r'os' + r'mo|swift' + r'://|pdx[.]s8k|AUTH_' + r'team|isaac-' + r'dev-|am' + r'lfs-', re.I),
    'workstation path': re.compile(r'/ho' + r'me/[^/\s]+|/mnt/' + r'amlfs'),
    'credential material': re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{25,}|BEGIN (?:RSA |OPENSSH )?PRIVATE' + r' KEY'),
}


def main():
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    failures = []
    for relative in filter(None, files):
        path = ROOT / relative
        if not path.is_file():
            continue
        text = relative + '\n' + path.read_bytes().decode(errors='replace')
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f'{relative}: {label}')
    if failures:
        # Report locations only; never echo matched credentials or internal URLs.
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print('Public source check passed: no prohibited infrastructure, workstation paths or credential patterns.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
