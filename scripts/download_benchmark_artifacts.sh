#!/usr/bin/env bash
# Download the released SO-101 typing checkpoints and their matched contracts.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/download_benchmark_artifacts.sh [OUTPUT_DIR]

Downloads the immutable checkpoint/config/evaluation bundle from:
  https://huggingface.co/datasets/VigneshBhavan/so101-keyboard-typing-benchmark

If OUTPUT_DIR is omitted, files are placed under .artifacts/ in this checkout.
Every downloaded file is verified against the release SHA-256 values before it
is installed in the output directory.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

[[ $# -le 1 ]] || { usage >&2; exit 2; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-${SO101_ARTIFACT_DIR:-$repo_root/.artifacts/so101-keyboard-typing-benchmark}}"
output_dir="$(mkdir -p "$output_dir" && realpath "$output_dir")"
base_url="${SO101_HF_BASE_URL:-https://huggingface.co/datasets/VigneshBhavan/so101-keyboard-typing-benchmark/resolve/main}"

command -v sha256sum >/dev/null || { echo "ERROR: sha256sum is required" >&2; exit 1; }
if command -v curl >/dev/null; then
  downloader="curl"
elif command -v wget >/dev/null; then
  downloader="wget"
else
  echo "ERROR: curl or wget is required" >&2
  exit 1
fi

die() {
  echo "ERROR: $*" >&2
  exit 1
}

download_and_verify() {
  local relative_path="$1"
  local expected_sha256="$2"
  local destination="$output_dir/$relative_path"
  local temporary actual_sha256

  mkdir -p "$(dirname "$destination")"
  if [[ -f "$destination" ]]; then
    actual_sha256="$(sha256sum "$destination" | awk '{print $1}')"
    if [[ "$actual_sha256" == "$expected_sha256" ]]; then
      printf '[OK] %s\n' "$relative_path" >&2
      return
    fi
    printf '[INFO] replacing checksum-mismatched %s\n' "$relative_path" >&2
  fi

  temporary="$(mktemp "$destination.partial.XXXXXX")"
  if [[ "$downloader" == "curl" ]]; then
    if ! curl --fail --location --silent --show-error --retry 3 --retry-delay 1 \
      --output "$temporary" "$base_url/$relative_path"; then
      rm -f "$temporary"
      die "download failed: $relative_path"
    fi
  elif ! wget --quiet --output-document="$temporary" "$base_url/$relative_path"; then
    rm -f "$temporary"
    die "download failed: $relative_path"
  fi

  actual_sha256="$(sha256sum "$temporary" | awk '{print $1}')"
  if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    rm -f "$temporary"
    die "checksum mismatch for $relative_path: expected $expected_sha256, got $actual_sha256"
  fi
  mv "$temporary" "$destination"
  printf '[OK] %s\n' "$relative_path" >&2
}

# This is the 2026-07-31 benchmark bundle. Keep the mapping explicit because
# the published SHA256SUMS file contains the publisher's original absolute
# paths, which are not valid on a recipient's machine.
artifacts=(
  'README.md|a28f44a1b4e1e67ea470aa6854890fbd6853fcec586cab8f8eeabb92873b9b40'
  'manifest.json|cf3ff2875e360c9aaf2a875a6eda7c90755e3b1c1f175fe4ab8e5bf0f594384d'
  'SHA256SUMS|7a9d8aa8867caa5e5a0cccdf74cac6137e30448b28ee8aca0095edee8ec8b836'
  'checkpoints/mjwarp-anchorbench-19k/model_19000.pt|239d93c99cd282e9add019f4ac952407c97fde2879821103a2aa7bd7a307a15f'
  'checkpoints/mjwarp-usd-19k/model_19000.pt|cc7f128e15a282a6f2fcc68e97f67c2e6f81bf6e03347b6a3cbf0b9a02d072a4'
  'checkpoints/mjwarp-workshop-19k/model_19000.pt|92cce575dad46f40f237060a509723d2c80a81c806f40dd1f6bfc41f44ce5910'
  'checkpoints/sparse-vbd-anchorbench-20k/model_19999.pt|d35c146f2bffcbb5f2dc91c8da560365e6ef64586e1e42f832932b9098a55487'
  'configs/mjwarp-anchorbench-19k.env.yaml|d4766dacb28a4ffc0fc75efe8e5abed162e656b338b110e8d498cc808e31ef8b'
  'configs/mjwarp-usd-19k.env.yaml|d14d60d19554326d66cbffc175c42166232968380980574ae36c196c9a0f7acb'
  'configs/mjwarp-workshop-19k.env.yaml|6c0c5a5f3a71159578b2ee69d5b379bc5482f1ad41eff7ac42ae30dccf96913b'
  'configs/sparse-vbd-anchorbench-20k.env.yaml|55215c907ce8b12c7b762c8eab2903790420cbbecd84a29bf88536df0da8ab2a'
  'evaluation/mjwarp-anchorbench-19k.corpus_100x6_seed1307.json|0598e2f235bcd3e2279c08a9c6e75934b47e84b58553b21dfd0e0089b57ac66a'
  'evaluation/mjwarp-usd-19k.corpus_100x6_seed1307.json|9db2f161f5bebac4b5a4dd5c9457d13fe0eeadf8eb3e2e01b42d8358a3ef0305'
  'evaluation/mjwarp-workshop-19k.strict_1024_seed1307.json|b07039e361600770e68e982344c0be7fa8f789b23039acce2dddda2457812a38'
  'evaluation/sparse-vbd-anchorbench-20k.corpus_100x6_seed1307.json|cdee2f512067a5d6bbcd31537c6aa45f59cf97e8f9d98ad0d4e4e748c3eb23ca'
  'evaluation/three_way_mjwarp19k_vbd20k_usd19k_orange2.summary.json|7a42e969ab1302ab89833f430dfd7606fb7bb4e801e6ee4ca4806886d02d9b1b'
)

for specification in "${artifacts[@]}"; do
  IFS='|' read -r relative_path expected_sha256 <<< "$specification"
  download_and_verify "$relative_path" "$expected_sha256"
done

printf '%s\n' "$output_dir"
