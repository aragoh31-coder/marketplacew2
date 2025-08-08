#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Starting backup..."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"

mkdir -p "$BACKUP_DIR"

echo "📦 Backing up database..."
docker-compose exec -T postgres pg_dump -U postgres marketplace > "$BACKUP_DIR/db_$TIMESTAMP.sql"

echo "📦 Backing up Redis..."
docker-compose exec -T redis redis-cli --rdb /tmp/dump.rdb
docker-compose exec -T redis cat /tmp/dump.rdb > "$BACKUP_DIR/redis_$TIMESTAMP.rdb"

echo "🧹 Cleaning old backups (>7 days)..."
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete

echo "✅ Backup complete: $TIMESTAMP"
