#!/bin/bash
set -e
python -m venv .venv
[ -f .venv/Scripts/activate ] && . .venv/Scripts/activate || [ -f .venv/bin/activate ] && . .venv/bin/activate
python -m pip install wheel
python -m pip install \
  --extra-index-url=https://wheels.eeems.codes/ \
  -r requirements.txt
python test.py
