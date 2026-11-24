#!/usr/bin/env bash
# Lance un tir k6 dans le cluster (Job) et récupère le résumé.
# Usage : scripts/run-load.sh <label> <script.js> [RATE] [DURATION] [MAX_RATE]
#   ex. scripts/run-load.sh nominal order-constant.js 50 3m
#       scripts/run-load.sh saturation order-ramp.js 0 0 150
set -euo pipefail
cd "$(dirname "$0")/.."
K() { if [ -n "${KUBECONFIG_INTERNAL:-}" ]; then scripts/kt.sh kubectl "$@"; else kubectl "$@"; fi; }

LABEL=$1; SCRIPT=$2; RATE=${3:-50}; DURATION=${4:-3m}; MAX_RATE=${5:-150}
NS=perf-lab; mkdir -p results

K create configmap k6-scripts -n "$NS" --from-file=load-tests/ --dry-run=client -o yaml | K apply -f - >/dev/null
K delete job k6-load -n "$NS" --ignore-not-found >/dev/null
sed -e "s|\${SCRIPT}|$SCRIPT|" -e "s|\${RATE}|$RATE|" -e "s|\${DURATION}|$DURATION|" \
    -e "s|\${MAX_RATE}|$MAX_RATE|" -e "s|\${LABEL}|$LABEL|" k8s/k6/k6-job.yaml | K apply -f - >/dev/null

START=$(date +%s)
echo ">> tir k6 '$LABEL' ($SCRIPT) démarré à $(date -d @"$START" '+%H:%M:%S')"
K wait --for=condition=complete job/k6-load -n "$NS" --timeout=1200s >/dev/null || true
END=$(date +%s)
K logs job/k6-load -n "$NS" | tee "results/$LABEL-k6.txt"
echo "{\"label\":\"$LABEL\",\"start\":$START,\"end\":$END}" > "results/$LABEL-window.json"
echo ">> fenêtre : $START -> $END"
