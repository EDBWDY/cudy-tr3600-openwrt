#!/bin/bash
# Stop before the hosted-runner limit so a checkpoint can still be uploaded.
set -euo pipefail
stage=${1:?tools, rust or firmware required}
cd "$(dirname "$0")/../openwrt"
case "$stage" in
  tools) targets=(tools/install toolchain/install);;
  rust) targets=(package/feeds/packages/rust/host/compile);;
  firmware) targets=();;
  *) echo "Unknown stage" >&2; exit 2;;
esac
set +e
timeout --signal=TERM --kill-after=120s 285m make -j2 V=s "${targets[@]}" 2>&1 | tee "../build-${stage}.log"
pipeline=("${PIPESTATUS[@]}")
status=${pipeline[0]}
if [[ "$status" == 0 && "${pipeline[1]}" != 0 ]]; then
  status=${pipeline[1]}
fi
set -e
echo "$status" > "../compile-${stage}.status"
if [[ "$status" == 124 ]]; then
  echo "Stage time budget reached; preserving partial work for continuation."
  # Tools/Rust continuation happens in the following job using the full tree.
  [[ "$stage" != firmware ]] && exit 0
fi
exit "$status"
