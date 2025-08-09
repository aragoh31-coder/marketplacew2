#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ONION_HOST="${ONION_HOST:-677ocptjrtgais5duw3ilnpiehyalubowul42g24s4p4hwy3ed5xchqd.onion}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
mkdir -p "$LOG_DIR"

echo "[1/6] Ensuring stack is up..."
docker compose up -d
docker compose ps

echo "[2/6] Applying migrations and collecting static..."
docker compose exec -T django python manage.py migrate --noinput || true
docker compose exec -T django python manage.py collectstatic --noinput || true

echo "[3/6] Warm-up probes..."
curl -sI -H "Host: $ONION_HOST" http://127.0.0.1/ | tr -d "\r" | sed -n '1,20p' || true
curl -sI -H "Host: $ONION_HOST" http://127.0.0.1/anti_ddos/spinner/ | tr -d "\r" | sed -n '1,20p' || true

echo "[4/6] Starting monitor (background)..."
python3 ddos_monitor.py > "$LOG_DIR/monitor.txt" 2>&1 & MONITOR_PID=$!

cleanup() {
  echo "Stopping monitor..."
  kill "$MONITOR_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[5/6] Running stress tests..."
python3 stress_test_antiddos.py > "$LOG_DIR/stress_report.txt" 2>&1 || true

echo "[6/6] Capturing logs and stats..."
docker compose logs --tail=300 openresty > "$LOG_DIR/openresty_tail.log" 2>&1 || true
docker compose logs --tail=300 django > "$LOG_DIR/django_tail.log" 2>&1 || true
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" > "$LOG_DIR/docker_stats.txt" 2>&1 || true

echo "Artifacts written to: $LOG_DIR"
