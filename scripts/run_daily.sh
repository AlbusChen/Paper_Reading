#!/bin/bash
# Daily paper collection runner
# Called by cron at 09:30 CST (01:30 UTC)

set -euo pipefail

CODEX=/raid/longhorn/huangchen/anaconda3/bin/codex
PYTHON=/raid/longhorn/huangchen/anaconda3/bin/python3
GIT=/usr/bin/git
REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
LOG_DIR="${REPO_DIR}/papers/logs"
DATE="${PAPER_DATE:-$(date -d "yesterday" +%Y-%m-%d)}"
LOGFILE="${LOG_DIR}/${DATE}.log"
DIGEST_JSON="/tmp/papers_${DATE}.json"
LOCK_FILE="/tmp/paper-reading-daily.lock"

# Cron has a minimal environment. Node comes from Anaconda and this server's
# GitHub SSH client is under /usr/local/bin.
export PATH="/raid/longhorn/huangchen/anaconda3/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PAPER_DATE="${DATE}"

mkdir -p "${LOG_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[$(date)] Another paper-reading daily run holds ${LOCK_FILE}; exiting." >&2
  exit 1
fi

exec > >(tee "${LOGFILE}") 2>&1

echo "[$(date)] Starting daily paper collection for ${DATE}"
cd "${REPO_DIR}"

echo "[$(date)] Updating repository..."
"${GIT}" pull --ff-only origin main

echo "[$(date)] Fetching paper metadata..."
"${PYTHON}" scripts/fetch_papers.py \
  --date "${DATE}" \
  --include-2026-focus \
  --output "${DIGEST_JSON}"

echo "[$(date)] Applying persistent summary cache..."
"${PYTHON}" scripts/summary_cache.py apply "${DIGEST_JSON}"

echo "[$(date)] Generating bilingual summaries with Codex..."
"${CODEX}" exec \
  --ephemeral \
  --cd "${REPO_DIR}" \
  --dangerously-bypass-approvals-and-sandbox \
  - < scripts/daily_prompt.md

# Fail closed: no HTML, commit, or push is allowed unless every fetched/HF
# record has valid bilingual summaries and HF metadata is healthy.
echo "[$(date)] Validating digest..."
"${PYTHON}" scripts/validate_digest.py "${DIGEST_JSON}"
"${PYTHON}" scripts/summary_cache.py update "${DIGEST_JSON}"

echo "[$(date)] Generating HTML..."
"${PYTHON}" scripts/generate_html.py "${DIGEST_JSON}"

echo "[$(date)] Committing and pushing..."
"${GIT}" add \
  papers/*.html \
  papers/*/*.html \
  papers/summary_cache.json \
  index.html
if ! "${GIT}" diff --cached --quiet; then
  "${GIT}" commit -m "Daily digest ${DATE}" \
    --author="Codex Bot <noreply@openai.com>"
fi
"${GIT}" push origin main

local_sha=$("${GIT}" rev-parse HEAD)
remote_sha=$("${GIT}" ls-remote origin refs/heads/main | awk '{print $1}')
if [[ -z "${remote_sha}" || "${local_sha}" != "${remote_sha}" ]]; then
  echo "[$(date)] Remote verification failed: origin/main does not match local HEAD." >&2
  exit 1
fi

echo "[$(date)] Done. Verified origin/main at ${local_sha}."
