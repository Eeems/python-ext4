#!/bin/bash
set -e

tmp_dir=$(mktemp -d)
echo "hello world" > "$tmp_dir"/test.txt
for i in {1..100};do
  echo "hello world$i" >> "$tmp_dir"/test$i.txt
  for j in {1..20};do
    setfattr -n user.name$j -v value${i}_$j "$tmp_dir"/test$i.txt
  done
done
trap "rm -r test.ext4{,.tmp}" EXIT
dd if=/dev/zero of=test.ext4.tmp count=20 bs=1048576
mkfs.ext4 -g 1024 test.ext4.tmp -d "$tmp_dir"
trap "rm -r \"$tmp_dir\"" EXIT
echo -n F > test.ext4
cat test.ext4.tmp >> test.ext4
