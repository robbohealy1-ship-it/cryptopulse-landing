#!/bin/bash

# CRYPTO PULSE SIGNALS - Backup Script

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="cryptopulse_backup_$DATE.tar.gz"

echo "📦 Creating backup..."

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup files
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
    --exclude='logs/*' \
    --exclude='data/*' \
    --exclude='charts/*' \
    --exclude='backups/*' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    .

echo "✅ Backup created: $BACKUP_DIR/$BACKUP_FILE"

# Keep only last 7 backups
cd $BACKUP_DIR
ls -t cryptopulse_backup_*.tar.gz | tail -n +8 | xargs -r rm

echo "✅ Old backups cleaned up"
echo "📊 Current backups:"
ls -lh cryptopulse_backup_*.tar.gz
