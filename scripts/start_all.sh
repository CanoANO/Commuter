#!/usr/bin/env bash
set -euo pipefail

shutdown() {
  echo "Stopping all processes..."
  kill -TERM "$WEB_PID" "$COLLECTOR_PID" "$ANALYZER_PID" 2>/dev/null || true
  wait "$WEB_PID" "$COLLECTOR_PID" "$ANALYZER_PID" 2>/dev/null || true
}

trap shutdown SIGTERM SIGINT

echo "Starting web service..."
GUNICORN_BIND="${WEB_GUNICORN_BIND:-0.0.0.0:8000}"
gunicorn -b "$GUNICORN_BIND" --workers "${WEB_GUNICORN_WORKERS:-2}" --timeout "${WEB_GUNICORN_TIMEOUT:-120}" --chdir /app/applications/web_app src.app:app &
WEB_PID=$!

echo "Starting data_collector worker..."
python -m applications.data_collector.worker &
COLLECTOR_PID=$!

echo "Starting data_analyzer worker..."
python -m applications.data_analyzer.worker &
ANALYZER_PID=$!

set +e
wait -n "$WEB_PID" "$COLLECTOR_PID" "$ANALYZER_PID"
EXIT_CODE=$?
set -e

echo "One process exited with code $EXIT_CODE, shutting down others..."
shutdown

exit "$EXIT_CODE"
