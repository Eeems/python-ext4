#!/bin/bash
set -e
python -m venv .venv
if [ -f .venv/Scripts/activate ]; then
  . .venv/Scripts/activate
elif [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
else
  echo "venv missing"
  exit 1
fi
python -m pip install wheel
python -m pip install \
  --extra-index-url=https://wheels.eeems.codes/ \
  -r requirements.txt
if ! [ -f test.ext4 ];then
  tmp_dir=$(mktemp -d)
  trap "rm -r \"$tmp_dir\"" EXIT
  echo "hello world" > "$tmp_dir"/test.txt
  for i in {1..100};do
    echo "hello world" >> "$tmp_dir"/test.txt
  done
  dd if=/dev/zero of=test.ext4 count=1024 bs=1024
  trap "rm test.ext4" EXIT
  mkfs.ext4 test.ext4 -d "$tmp_dir"
fi
python test.py
