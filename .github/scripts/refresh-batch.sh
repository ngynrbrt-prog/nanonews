#!/usr/bin/env bash
set -euo pipefail

mode=$1
time_limit=$2
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git pull --ff-only origin main

echo "Starting NANONews batch: $mode"
NANONEWS_MODE="$mode" timeout --kill-after=10s "$time_limit" python -u refresh_news.py
git add -- data/
if git diff --cached --quiet; then
  echo "No data changes: $mode"
  exit 0
fi

echo "Saving NANONews batch: $mode"
git commit -m "NANONews: $mode"
for attempt in 1 2 3; do
  git pull --rebase origin main
  if git push origin HEAD:main; then
    echo "Saved NANONews batch: $mode"
    exit 0
  fi
done
exit 1
