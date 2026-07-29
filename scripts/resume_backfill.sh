#!/bin/bash
# Resume an already initialized chronological backfill and publish on success.

set -euo pipefail

if [[ $# -ne 2 || ! "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ || ! "$2" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Usage: $0 START_DATE END_DATE" >&2
  exit 2
fi

START_DATE="$1"
END_DATE="$2"
MONTH="${START_DATE:0:7}"
REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
PYTHON=/raid/longhorn/huangchen/anaconda3/bin/python3
GIT=/usr/bin/git
export PATH="/raid/longhorn/huangchen/anaconda3/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

if [[ "${END_DATE:0:7}" != "${MONTH}" ]]; then
  echo "START_DATE and END_DATE must be in the same month" >&2
  exit 2
fi

cd "${REPO_DIR}"
mapfile -t DATES < <("${PYTHON}" - "${START_DATE}" "${END_DATE}" <<'PY'
import sys
from datetime import date, timedelta

current = date.fromisoformat(sys.argv[1])
end = date.fromisoformat(sys.argv[2])
today = date.today()
if end < current:
    raise SystemExit("END_DATE must not precede START_DATE")
if end >= today:
    raise SystemExit("END_DATE must be before today")
while current <= end:
    print(current.isoformat())
    current += timedelta(days=1)
PY
)

for digest_date in "${DATES[@]}"; do
  echo "===== Resuming ${digest_date} ====="
  PAPER_DATE="${digest_date}" \
  PAPER_PULL=0 \
  PAPER_PUBLISH=0 \
    scripts/run_daily.sh
done

"${PYTHON}" scripts/validate_month.py "${MONTH}"

"${GIT}" add \
  papers/*.html \
  papers/*/*.html \
  papers/summary_cache.json \
  papers/seen_papers.json \
  index.html
if ! "${GIT}" diff --cached --quiet; then
  "${GIT}" commit -m "Backfill bilingual digests ${MONTH}" \
    --author="Codex Bot <noreply@openai.com>"
fi
"${GIT}" push origin main

local_sha=$("${GIT}" rev-parse HEAD)
remote_sha=$("${GIT}" ls-remote origin refs/heads/main | awk '{print $1}')
test -n "${remote_sha}"
test "${local_sha}" = "${remote_sha}"
echo "Backfill complete and verified at ${local_sha}"
