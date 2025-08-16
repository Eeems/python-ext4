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
if ! [ -f test32.ext4 ] || ! [ -f test32.ext4.tmp ] || ! [ -f test64.ext4 ] || ! [ -f test64.ext4.tmp ] ;then
  ./_test_image.sh
  trap "rm -f test{32,64}.ext4{,.tmp}" EXIT
fi
python test.py
