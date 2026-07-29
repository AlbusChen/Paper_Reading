#!/bin/bash
# Rebuild a month chronologically, publishing only after every day succeeds.

set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
  echo "Usage: $0 YYYY-MM" >&2
  exit 2
fi

MONTH="$1"
REPO_DIR="/raid/longhorn/huangchen/Paper_Reading"
PYTHON=/raid/longhorn/huangchen/anaconda3/bin/python3
GIT=/usr/bin/git
export PATH="/raid/longhorn/huangchen/anaconda3/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

cd "${REPO_DIR}"
test -z "$("${GIT}" status --porcelain)"
"${GIT}" pull --ff-only origin main

FIRST_DATE="${MONTH}-01"
"${PYTHON}" scripts/deduplicate_papers.py rebuild \
  --papers-dir papers \
  --before "${FIRST_DATE}"

mapfile -t DATES < <("${PYTHON}" - "${MONTH}" <<'PY'
import calendar
import sys
from datetime import date

year, month = map(int, sys.argv[1].split("-"))
last_day = calendar.monthrange(year, month)[1]
today = date.today()
for day in range(1, last_day + 1):
    candidate = date(year, month, day)
    if candidate >= today:
        break
    print(candidate.isoformat())
PY
)

for digest_date in "${DATES[@]}"; do
  echo "===== Backfilling ${digest_date} ====="
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
