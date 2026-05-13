#!/bin/bash
# Daily paper collection runner
# Called by cron at 09:30 CST (01:30 UTC)

set -euo pipefail

REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
LOG_DIR="${REPO_DIR}/papers/logs"
DATE=$(date -d "yesterday" +%Y-%m-%d)
LOGFILE="${LOG_DIR}/${DATE}.log"

mkdir -p "${LOG_DIR}"

echo "[$(date)] Starting daily paper collection for ${DATE}" | tee "${LOGFILE}"

# Run claude with the daily prompt
cd "${REPO_DIR}"
claude --dangerouslySkipPermissions -p "$(cat scripts/daily_prompt.md)" >> "${LOGFILE}" 2>&1

echo "[$(date)] Done." | tee -a "${LOGFILE}"
