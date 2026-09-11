#!/usr/bin/env bash
# Apply this focused source release to a compatible full Isaac Lab checkout.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/overlay_into_isaaclab.sh [--dry-run] /absolute/path/to/isaaclab

The target must be a full Isaac Lab checkout with isaaclab.sh. The overlay
updates only the released source, scripts, Docker workflow files, deployment
documentation, and fixture guide; it does not copy checkpoints or private
hardware calibration.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi
[[ $# -eq 1 ]] || { usage >&2; exit 2; }

release_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(realpath -e "$1")"

[[ -x "$target/isaaclab.sh" ]] || {
  echo "ERROR: target does not look like a full Isaac Lab checkout: $target" >&2
  exit 1
}
[[ "$target" != "$release_root" ]] || {
  echo "ERROR: target cannot be the focused release checkout itself" >&2
  exit 1
}
command -v rsync >/dev/null || {
  echo "ERROR: rsync is required for a safe overlay" >&2
  exit 1
}

if git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if ! git -C "$target" diff --quiet || ! git -C "$target" diff --cached --quiet; then
    echo "ERROR: target has uncommitted changes; commit or stash them before overlaying" >&2
    exit 1
  fi
fi

rsync_args=(-a)
if "$dry_run"; then
  rsync_args+=(--dry-run --itemize-changes)
fi

rsync "${rsync_args[@]}" "$release_root/source/" "$target/source/"
rsync "${rsync_args[@]}" "$release_root/scripts/" "$target/scripts/"
rsync "${rsync_args[@]}" "$release_root/docker/" "$target/docker/"
rsync "${rsync_args[@]}" "$release_root/docs/source/policy_deployment/06_so101_keyboard/" \
  "$target/docs/source/policy_deployment/06_so101_keyboard/"

if "$dry_run"; then
  printf '[DRY-RUN] would copy %s\n' "$release_root/FIXTURE_SETUP.md"
else
  install -m 0644 "$release_root/FIXTURE_SETUP.md" "$target/FIXTURE_SETUP.md"
  printf '[OK] SO-101 keyboard task overlay applied to %s\n' "$target"
  printf '%s\n' 'Next: run the focused tests and the Newton contract probe from the target checkout.'
fi
