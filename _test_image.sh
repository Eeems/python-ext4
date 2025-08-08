#!/bin/bash
set -e

tmp_dir=$(mktemp -d)
trap "rm -r \"$tmp_dir\"" EXIT
echo "hello world" > "$tmp_dir"/test.txt
for i in {1..100};do
  echo "hello world$i" >> "$tmp_dir"/test$i.txt
  for j in {1..20};do
    setfattr -n user.name$j -v value${i}_$j "$tmp_dir"/test$i.txt
  done
done
rm -r test{32,64}.ext4{,.tmp}
dd if=/dev/zero of=test32.ext4.tmp count=20 bs=1048576
dd if=/dev/zero of=test64.ext4.tmp count=20 bs=1048576
mkfs.ext4 -g 1024 -O 64bit test64.ext4.tmp -d "$tmp_dir"
mkfs.ext4 -g 1024 -O ^64bit test32.ext4.tmp -d "$tmp_dir"
echo -n F > test32.ext4
cat test32.ext4.tmp >> test32.ext4
echo -n F > test64.ext4
cat test64.ext4.tmp >> test64.ext4
