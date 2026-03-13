#!/bin/bash
set -e

if ! command -v chronic &>/dev/null; then
  chronic() {
    "$@"
  }
fi

mkimage() {
  name="$1"
  shift
  dir="$1"
  shift
  size="$1"
  shift

  echo "[test] Making image $name < $dir..."
  chronic dd if=/dev/zero of="$name".ext4.tmp count="$size" bs=1048576
  chronic mkfs.ext4 -g 1024 "$@" "$name".ext4.tmp -d "$dir"
  echo -n F >"$name".ext4
  cat "$name".ext4.tmp >>"$name".ext4
}

tmp_dir=$(mktemp -d)
# shellcheck disable=SC2064
trap "rm -r \"$tmp_dir\"" EXIT
echo "[test] Using temporary directory: $tmp_dir"
echo "[test] Generating files..."
echo "hello world" >"$tmp_dir"/test.txt
for i in {1..1000}; do
  echo "echo "hello world" >>'$tmp_dir/test.txt'"
done | xargs -P "$(nproc)" -I {} bash -c '{}'
for i in {1..100}; do
  echo "echo 'hello world$i' >'$tmp_dir/test$i.txt'"
done | xargs -P "$(nproc)" -I {} bash -c '{}'
for i in {1..100}; do
  for j in {1..20}; do
    echo "setfattr -n 'user.name$j' -v 'value${i}_$j' '$tmp_dir/test$i.txt'"
  done
done | xargs -P "$(nproc)" -I {} bash -c '{}'

mkimage test32 "$tmp_dir" 20 -O ^64bit
mkimage test64 "$tmp_dir" 20 -O 64bit

rm -f "$tmp_dir"/test*.txt
echo "[test] Generating files..."

echo "[test] Making image $name..."
chronic dd if=/dev/zero of=test_htree.ext4 count=20 bs=1048576
chronic mkfs.ext4 -g 1024 -b 1024 -O 64bit,dir_index test_htree.ext4
sudo mount -t ext4 test_htree.ext4 "$tmp_dir"
# shellcheck disable=SC2064
trap "sudo umount;rmdir \"$tmp_dir\"" EXIT
sudo mkdir "$tmp_dir"/empty
printf '%s\n' "$tmp_dir"/{1..200} | xargs sudo touch
sudo umount "$tmp_dir"
# shellcheck disable=SC2064
trap "rmdir \"$tmp_dir\"" EXIT
chronic e2fsck -Dy test_htree.ext4
