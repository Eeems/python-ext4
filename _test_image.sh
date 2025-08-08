#!/bin/bash
set -e

tmp_dir=$(mktemp -d)
trap "rm -r \"$tmp_dir\"" EXIT
echo "hello world" > "$tmp_dir"/test.txt
for i in {1..100};do
  echo "hello world" >> "$tmp_dir"/test.txt
done
dd if=/dev/zero of=test.ext4.tmp count=1024 bs=1024
mkfs.ext4 test.ext4.tmp -d "$tmp_dir"
echo -n F > test.ext4
cat test.ext4.tmp >> test.ext4
