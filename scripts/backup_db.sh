#!/bin/bash
# Run after any major ingestion to backup the DB
BACKUP_DIR=~/enterprise-knowledge-copilot/data/backups
mkdir -p $BACKUP_DIR
docker exec ekc_postgres pg_dump -U ekc_user ekc_db > $BACKUP_DIR/ekc_db_$(date +%Y%m%d_%H%M).sql
echo "Backup saved to $BACKUP_DIR"
