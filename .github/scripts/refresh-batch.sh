#!/usr/bin/env bash
set -euo pipefail

mode=$1
time_limit=$2
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
if [[ "$mode" == official ]]; then
  export NANONEWS_SNAPSHOT_REF=origin/main
  # A scheduled run can start a few minutes before the edition cutoff.
  # Wait before pulling main so the cutoff snapshot is available locally.
  read -r hour minute second <<< "$(TZ=Europe/Budapest date '+%H %M %S')"
  seconds_today=$((10#$hour * 3600 + 10#$minute * 60 + 10#$second))
  for slot_hour in 5 16; do
    seconds_until_slot=$((slot_hour * 3600 - seconds_today))
    if (( seconds_until_slot > 0 && seconds_until_slot <= 240 )); then
      echo "Waiting ${seconds_until_slot}s for the NANONews edition cutoff."
      sleep "$seconds_until_slot"
      break
    fi
  done
fi

refresh_window_open() {
  local hour minute slot delta
  read -r hour minute <<< "$(TZ=Europe/Budapest date '+%H %M')"
  minute=$((10#$hour * 60 + 10#$minute))
  for slot in 300 960; do
    delta=$((slot - minute))
    if (( delta <= 8 && delta >= -4 )); then
      return 1
    fi
  done
}

for attempt in 1 2 3; do
  if [[ "$mode" != official ]] && ! refresh_window_open; then
    echo "Edition window: deferring NANONews batch $mode."
    exit 0
  fi
  git pull --ff-only origin main
  base=$(git rev-parse HEAD)
  echo "Starting NANONews batch: $mode"
  NANONEWS_MODE="$mode" timeout --foreground --kill-after=10s "$time_limit" python -u refresh_news.py
  git add -- data/
  if git diff --cached --quiet; then
    echo "No data changes: $mode"
    exit 0
  fi

  echo "Saving NANONews batch: $mode"
  git commit -m "NANONews: $mode"
  if git pull --rebase origin main; then
    if git push origin HEAD:main; then
      echo "Saved NANONews batch: $mode"
      exit 0
    fi
  elif ! git rebase --abort; then
    exit 1
  fi
  # Recompute against the new edition if another workflow committed concurrently.
  git reset --hard "$base"
done
exit 1
