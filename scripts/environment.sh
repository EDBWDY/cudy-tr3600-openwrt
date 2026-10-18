#!/bin/bash
set -euo pipefail
# Retain the hosted runner's current Node binary before removing SDK caches.
node_source=$(readlink -f "$(command -v node)")
mkdir -p "$RUNNER_TEMP/tr3600-node/bin"
cp "$node_source" "$RUNNER_TEMP/tr3600-node/bin/node"
echo "$RUNNER_TEMP/tr3600-node/bin" >> "$GITHUB_PATH"
# Only disposable GitHub runner tools; Actions' own Node runtime is retained.
sudo rm -rf /usr/local/lib/android /usr/share/dotnet /opt/ghc \
  /opt/hostedtoolcache /usr/local/.ghcup /usr/share/swift \
  /usr/local/share/powershell /usr/local/share/boost /usr/local/share/chromium \
  /opt/google /opt/microsoft /opt/pipx /home/runner/.rustup /home/runner/.cargo
sudo apt-get update
# Remove only installed optional SDK packages, then reinstall required
# build dependencies below. This is an ephemeral hosted runner.
mapfile -t unused_packages < <(dpkg-query -W -f='${binary:Package}\n' | \
  grep -E '^(llvm-[0-9]+|clang-[0-9]+|libllvm[0-9]+|temurin-.*|openjdk-.*|dotnet-.*|aspnetcore-.*|mono-.*|azure-cli|powershell)(:.*)?$')
if (( ${#unused_packages[@]} )); then
  sudo apt-get purge -y "${unused_packages[@]}"
fi
sudo apt-get autoremove -y
sudo apt-get install -y build-essential clang flex bison gawk gettext git \
  libncurses-dev libssl-dev rsync unzip zlib1g-dev file wget xz-utils \
  libelf-dev python3 python3-setuptools python3-distutils swig curl \
  ca-certificates subversion autoconf automake libtool pkgconf pigz \
  device-tree-compiler jq zstd python3-cryptography nodejs
sudo apt-get clean
df -h .
available=$(df --output=avail -B1 . | tail -n1 | tr -d ' ')
if (( available < 50 * 1024 * 1024 * 1024 )); then
  sudo du -x -h --max-depth=1 /usr /opt /home/runner 2>/dev/null | sort -h | tail -n20
  echo "Insufficient build disk: need 50 GiB free before source checkout"
  exit 1
fi
