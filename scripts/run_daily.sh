#!/bin/bash
# Daily paper collection runner
# Called by cron at 09:30 CST (01:30 UTC)

set -euo pipefail

CODEX=/raid/longhorn/huangchen/anaconda3/bin/codex
PYTHON=/raid/longhorn/huangchen/anaconda3/bin/python3
GIT=/usr/bin/git
REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
LOG_DIR="${REPO_DIR}/papers/logs"
DATE=$(date -d "yesterday" +%Y-%m-%d)
LOGFILE="${LOG_DIR}/${DATE}.log"
FALLBACK_JSON="/tmp/papers_${DATE}.json"

mkdir -p "${LOG_DIR}"

echo "[$(date)] Starting daily paper collection for ${DATE}" | tee "${LOGFILE}"

cd "${REPO_DIR}"
"${GIT}" pull --ff-only origin main >> "${LOGFILE}" 2>&1 || \
  echo "[$(date)] Warning: git pull failed; continuing with local checkout." | tee -a "${LOGFILE}"

if "${CODEX}" exec \
    --cd "${REPO_DIR}" \
    --dangerously-bypass-approvals-and-sandbox \
    --search \
    - < scripts/daily_prompt.md >> "${LOGFILE}" 2>&1; then
  echo "[$(date)] Codex summary workflow completed." | tee -a "${LOGFILE}"
else
  echo "[$(date)] Warning: Codex summary workflow failed; generating metadata-only digest." | tee -a "${LOGFILE}"
  "${PYTHON}" scripts/fetch_papers.py --date "${DATE}" --output "${FALLBACK_JSON}" >> "${LOGFILE}" 2>&1
  "${PYTHON}" scripts/generate_html.py "${FALLBACK_JSON}" >> "${LOGFILE}" 2>&1
fi

# Push to GitHub for GitHub Pages
echo "[$(date)] Pushing to GitHub..." | tee -a "${LOGFILE}"
"${GIT}" add papers/*.html papers/*/*.html index.html 2>/dev/null || true
"${GIT}" diff --cached --quiet || \
  "${GIT}" commit -m "Daily digest ${DATE}" \
    --author="Codex Bot <noreply@openai.com>" >> "${LOGFILE}" 2>&1
"${GIT}" push origin main >> "${LOGFILE}" 2>&1

echo "[$(date)] Done." | tee -a "${LOGFILE}"
