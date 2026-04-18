#!/bin/bash
set -e
libc=${libc:-glibc}
arch=${arch:-x86_64}
python=${python:-3.11}

wheel="$(find wheelhouse -name "*_${arch}.whl" | head -n1)"
if [[ -z "$wheel" ]]; then
  echo "No wheel found for architecture $arch"
  exit 1
fi
script=$(
  cat <<EOF
cd /src;
pip install "${wheel}"[test];
mkdir -p /tmp/test
cp \
  test.sh \
  test.py \
  test*.ext4 \
  test*.ext4.tmp \
  /tmp/test
cd /tmp/test;
python -u test.py;
EOF
)
if [[ "$libc" == "musl" ]]; then
  image="python:${python}-alpine"
  script="apk add --no-cache git;$script"
else
  image="python:${python}"
fi
case "$arch" in
i686)
  echo "WARNING: Unable to test i686 as there is no suitable python image. Skipping without error for now."
  exit 0
  ;;
riscv64)
  if [[ "$libc" == "glibc" ]]; then
    echo "WARNING: Unable to test riscv64 as the python image doesn't support manylinux. Skipping without error for now."
    exit 0
  fi
  platform="linux/${arch}"
  ;;
armv7l)
  platform="linux/arm/v7"
  ;;
*) platform="linux/${arch}" ;;
esac
if [[ "$arch" != "x86_64" ]]; then
  docker run \
    --privileged \
    --rm \
    tonistiigi/binfmt --install all
fi
docker run \
  --rm \
  --volume="$(pwd):/src" \
  --platform="$platform" \
  "$image" \
  /bin/sh -ec "$script"
