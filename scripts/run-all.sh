#!/usr/bin/env bash
# Enchaîne les 4 régimes du TP et extrait les métriques eBPF de Prometheus.
#   1. nominal        50 RPS / 3 min
#   2. errors         50 RPS / 3 min, 10 % de HTTP 500 sur pricing-engine
#   3. tail           50 RPS / 3 min, 95 % à 15 ms / 5 % à 600 ms
#   4. saturation     limite CPU 100m, paliers 25 -> 150 RPS (6 x 60 s)
# Prérequis : Prometheus joignable sur PROM_URL (défaut http://127.0.0.1:9091), ex. :
#   kubectl port-forward -n perf-lab svc/kps-kube-prometheus-stack-prometheus 9091:9090
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
GAP=${GAP:-75}   # pause entre deux tirs : les fenêtres rate[1m] ne se chevauchent pas

for s in nominal errors tail; do
  scripts/scenario.sh "$s"
  scripts/run-load.sh "$s" order-constant.js 50 3m
  python scripts/extract_metrics.py "$s" 170 > /dev/null
  sleep "$GAP"
done

scripts/scenario.sh saturation
scripts/run-load.sh saturation order-ramp.js 0 0 150
python scripts/extract_metrics.py saturation --steps:6x60 > /dev/null

scripts/scenario.sh nominal   # retour à l'état initial
echo "Résultats dans results/"
