#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Usage: $0 {p0|p1a|p1b|p1c|p1d|p1d-transit15|baseline-p1d-transit15|usd-drive-p1d-transit15} TARGET CHECKPOINT ENV_YAML REST_POSE" >&2
  exit 2
fi

recipe="$1"
target="$2"
checkpoint="$3"
env_config="$4"
rest_pose="$5"

case "$recipe" in
  p0)
    stage="p0"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p0_v0"
    ;;
  p1a)
    stage="p1a"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p1a_letters2_v0"
    ;;
  p1b)
    stage="p1b"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p1b_letters3_v0"
    ;;
  p1c)
    stage="p1c"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p1c_letters4_v0"
    ;;
  p1d)
    stage="p1d"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p1d_letters6_v0"
    ;;
  p1d-transit15)
    stage="p1d"
    actuator_profile="anchorbench"
    task_contract="physical_calibrated_20260718_fixed_cartesian_anchorbench_p1d_transit15_letters6_v0"
    ;;
  baseline-p1d-transit15)
    stage="p1d"
    actuator_profile="baseline"
    task_contract="physical_calibrated_20260718_fixed_cartesian_baseline_p1d_transit15_letters6_v0"
    ;;
  usd-drive-p1d-transit15)
    stage="p1d"
    actuator_profile="usd_drive"
    task_contract="physical_calibrated_20260718_fixed_cartesian_usd_drive_p1d_transit15_letters6_v0"
    ;;
  *)
    echo "Unknown physical typing recipe: $recipe" >&2
    exit 2
    ;;
esac

if [[ ! "$target" =~ ^[A-Za-z]+$ ]]; then
  echo "Target must contain only A-Z letters: $target" >&2
  exit 2
fi

for artifact in "$checkpoint" "$env_config" "$rest_pose"; do
  if [[ "$artifact" != /* || ! -f "$artifact" ]]; then
    echo "Artifact must be an existing absolute path: $artifact" >&2
    exit 2
  fi
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${SO101_LEROBOT_PYTHON:-python3}"
output_dir="${SO101_POLICY_OUTPUT_DIR:-$repo_root/output/so101_homing/policy_runs}"

if [[ "$python_bin" == */* ]]; then
  [[ -x "$python_bin" ]] || { echo "Python is not executable: $python_bin" >&2; exit 2; }
else
  command -v "$python_bin" >/dev/null || { echo "Python command not found: $python_bin" >&2; exit 2; }
fi

hardware_args=()
[[ -n "${SO101_KEYBOARD_DEVICE:-}" ]] && hardware_args+=(--device "$SO101_KEYBOARD_DEVICE")
[[ -n "${SO101_ROBOT_PORT:-}" ]] && hardware_args+=(--port "$SO101_ROBOT_PORT")
[[ -n "${SO101_ROBOT_ID:-}" ]] && hardware_args+=(--id "$SO101_ROBOT_ID")

case "${SO101_POLICY_DRY_RUN:-0}" in
  0) mode_args=(--enable-robot) ;;
  1) mode_args=(--dry-run) ;;
  *)
    echo "SO101_POLICY_DRY_RUN must be 0 or 1" >&2
    exit 2
    ;;
esac

mkdir -p "$output_dir"
cd "$repo_root"

exec "$python_bin" \
  -m scripts.so101_homing.run_fixed_cartesian_policy_handoff \
  --task-profile physical-calibrated-20260718 \
  --stage "$stage" \
  --target "$target" \
  --checkpoint "$checkpoint" \
  --env-config "$env_config" \
  --expected-actuator-profile "$actuator_profile" \
  --expected-task-contract "$task_contract" \
  --startup-mode fixed-reset \
  --rest-pose "$rest_pose" \
  "${hardware_args[@]}" \
  "${mode_args[@]}" \
  --start-joint-epsilon-deg 0.5 \
  --out "$output_dir/physical_calibrated_20260718_${recipe}_${target^^}_$(date +%Y%m%d_%H%M%S).jsonl"
