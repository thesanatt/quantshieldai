#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/monitor
LOG="data/monitor/deploy.log"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >> "$LOG" 2>&1
{
  echo "=== deploy $(date '+%Y-%m-%d %H:%M:%S') ==="
  ./venv/bin/python -m quantshield.live.export
  cp docs/research_report.pdf dashboard/public/research_report.pdf
  echo "research report copied to dashboard/public/research_report.pdf"
  (cd dashboard && npm run build && vercel deploy --prod --yes)
  echo "dashboard deployed $(date '+%Y-%m-%d %H:%M:%S')"
} >> "$LOG" 2>&1
echo "dashboard deployed $(date '+%Y-%m-%d %H:%M:%S')"
