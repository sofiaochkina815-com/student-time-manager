#!/bin/sh
set -eu
python -m pip install -r requirements.txt
python main.py collectstatic --noinput
