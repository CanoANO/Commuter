#!/usr/bin/env bash
set -euo pipefail

PIDS=()

shutdown() {
  echo "Stopping all processes..."
  if [[ ${#PIDS[@]} -gt 0 ]]; then
    kill -TERM "${PIDS[@]}" 2>/dev/null || true
    wait "${PIDS[@]}" 2>/dev/null || true
  fi
}

trap shutdown SIGTERM SIGINT

echo "Starting web service..."
GUNICORN_BIND="${WEB_GUNICORN_BIND:-0.0.0.0:8000}"
gunicorn \
  -c /app/applications/web_app/gunicorn.conf.py \
  -b "$GUNICORN_BIND" \
  --workers "${WEB_GUNICORN_WORKERS:-2}" \
  --timeout "${WEB_GUNICORN_TIMEOUT:-120}" \
  --chdir /app/applications/web_app \
  src.app:app &
WEB_PID=$!
PIDS+=("$WEB_PID")

JOB_BACKEND_NORMALIZED="$(echo "${JOB_BACKEND:-rabbitmq}" | tr '[:upper:]' '[:lower:]')"
EMBEDDED_CONSUMERS_NORMALIZED="$(echo "${EMBEDDED_CONSUMERS:-false}" | tr '[:upper:]' '[:lower:]')"

if [[ "$JOB_BACKEND_NORMALIZED" == "local" ]]; then
  echo "JOB_BACKEND=local, collector/analyzer handled in-process."
elif [[ "$EMBEDDED_CONSUMERS_NORMALIZED" == "true" ]]; then
  echo "EMBEDDED_CONSUMERS=true, consumer threads start inside gunicorn workers."
else
  echo "Starting data_collector worker..."
  python -m applications.data_collector.worker &
  COLLECTOR_PID=$!
  PIDS+=("$COLLECTOR_PID")

  echo "Starting data_analyzer worker..."
  python -m applications.data_analyzer.worker &
  ANALYZER_PID=$!
  PIDS+=("$ANALYZER_PID")
fi

set +e
wait -n "${PIDS[@]}"
EXIT_CODE=$?
set -e

echo "One process exited with code $EXIT_CODE, shutting down others..."
shutdown

exit "$EXIT_CODE"
