#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="/data/weewx"
CONFIG_FILE="$CONFIG_DIR/weewx.conf"

python /usr/local/bin/configure.py

python -m http.server 80 --directory "$CONFIG_DIR/public_html" &
http_pid=$!
weewxd --config "$CONFIG_FILE" &
weewx_pid=$!

stop_services() {
    kill "$http_pid" "$weewx_pid" 2>/dev/null || true
}
trap stop_services TERM INT EXIT

wait -n "$http_pid" "$weewx_pid"
