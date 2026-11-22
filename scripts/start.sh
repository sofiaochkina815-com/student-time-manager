#!/bin/sh
set -eu
python main.py migrate --noinput
exec python -m gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 2 --timeout 60 --access-logfile -
