#!/usr/bin/env python3
"""Reject infrastructure-specific files, machine paths and credential material."""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'cluster integration': re.compile(r'os' + r'mo|swift' + r'://|pdx[.]s8k|AUTH_' + r'team|isaac-' + r'dev-|am' + r'lfs-', re.I),
    'workstation path': re.compile(r'/ho' + r'me/[^/\s]+|/mnt/' + r'amlfs'),
    'credential material': re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{25,}|BEGIN (?:RSA |OPENSSH )?PRIVATE' + r' KEY'),
    'obsolete repository': re.compile(r'github[.]com/' + r'es-rl/so101' + r'_keyboard_task'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, help='also scan public bundle metadata and checkpoint pickle strings')
    args = parser.parse_args()
    files = [(ROOT / name, name) for name in subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if name]
    if args.artifact_dir:
        if not args.artifact_dir.is_dir():
            parser.error('artifact directory does not exist')
        files += [(path, 'artifacts/' + str(path.relative_to(args.artifact_dir)))
                  for path in args.artifact_dir.rglob('*')
                  if path.is_file() and '.cache' not in path.relative_to(args.artifact_dir).parts]
    failures = []
    for path, relative in files:
        if not path.is_file():
            continue
        if path.suffix == '.pt' and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                payload = b'\n'.join(archive.read(name) for name in archive.namelist() if name.endswith('.pkl'))
        elif path.suffix in ('.mp4', '.png', '.npz'):
            continue
        else:
            payload = path.read_bytes()
        text = relative + '\n' + payload.decode(errors='replace')
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
