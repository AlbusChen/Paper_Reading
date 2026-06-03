#!/bin/bash
# Daily paper collection runner
# Called by cron at 09:30 CST (01:30 UTC)

set -euo pipefail

CLAUDE=/raid/longhorn/huangchen/anaconda3/bin/claude
GIT=/usr/bin/git
REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
LOG_DIR="${REPO_DIR}/papers/logs"
DATE=$(date -d "yesterday" +%Y-%m-%d)
LOGFILE="${LOG_DIR}/${DATE}.log"

mkdir -p "${LOG_DIR}"

echo "[$(date)] Starting daily paper collection for ${DATE}" | tee "${LOGFILE}"

cd "${REPO_DIR}"
"${CLAUDE}" --dangerously-skip-permissions -p "$(cat scripts/daily_prompt.md)" >> "${LOGFILE}" 2>&1

# Push to GitHub for GitHub Pages
echo "[$(date)] Pushing to GitHub..." | tee -a "${LOGFILE}"
"${GIT}" add papers/*.html papers/*/*.html index.html 2>/dev/null || true
"${GIT}" diff --cached --quiet || \
  "${GIT}" commit -m "Daily digest ${DATE}" \
    --author="Claude Bot <noreply@anthropic.com>" >> "${LOGFILE}" 2>&1
"${GIT}" push origin main >> "${LOGFILE}" 2>&1

echo "[$(date)] Done." | tee -a "${LOGFILE}"
