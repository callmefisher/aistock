#!/bin/bash
set -e

DATA_DIR="/app/data"

if [ -d "$DATA_DIR" ]; then
    chown -R appuser:appuser "$DATA_DIR" 2>/dev/null || true
fi

mkdir -p "$DATA_DIR/excel" "$DATA_DIR/logs" "$DATA_DIR/cookies" 2>/dev/null || true
chown -R appuser:appuser "$DATA_DIR" 2>/dev/null || true

exec gosu appuser "$@"
