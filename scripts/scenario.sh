#!/usr/bin/env bash
# Configure pricing-engine pour un régime de test donné (variables d'environnement + ressources).
# Usage : scripts/scenario.sh nominal|errors|tail|saturation
# (utilise scripts/kt.sh si KUBECONFIG_INTERNAL est défini, sinon kubectl local)
set -euo pipefail
cd "$(dirname "$0")/.."
K() { if [ -n "${KUBECONFIG_INTERNAL:-}" ]; then scripts/kt.sh kubectl "$@"; else kubectl "$@"; fi; }

NS=perf-lab
case "${1:-}" in
  nominal)     # ~5-10 ms de traitement, aucune erreur, pas de limite CPU
    ENV="BASE_LATENCY_MS=5 JITTER_MS=5 SLOW_PERCENT=0 SLOW_LATENCY_MS=0 ERROR_RATE=0 CPU_ITERATIONS=0"
    LIMIT="cpu=0" ;;
  errors)      # 10 % de réponses HTTP 500
    ENV="BASE_LATENCY_MS=5 JITTER_MS=5 SLOW_PERCENT=0 SLOW_LATENCY_MS=0 ERROR_RATE=10 CPU_ITERATIONS=0"
    LIMIT="cpu=0" ;;
  tail)        # 95 % en 15 ms, 5 % en 600 ms (pause GC / verrou I/O simulé)
    ENV="BASE_LATENCY_MS=15 JITTER_MS=0 SLOW_PERCENT=5 SLOW_LATENCY_MS=600 ERROR_RATE=0 CPU_ITERATIONS=0"
    LIMIT="cpu=0" ;;
  saturation)  # travail CPU par requête + limite CPU à 100m
    ENV="BASE_LATENCY_MS=5 JITTER_MS=0 SLOW_PERCENT=0 SLOW_LATENCY_MS=0 ERROR_RATE=0 CPU_ITERATIONS=${CPU_ITERATIONS:-5000}"
    LIMIT="cpu=100m" ;;
  *) echo "usage: $0 nominal|errors|tail|saturation" >&2; exit 1 ;;
esac

echo ">> scénario '$1' : $ENV ; limits $LIMIT"
# shellcheck disable=SC2086
K set env deploy/pricing-engine -n "$NS" $ENV >/dev/null
if [ "$LIMIT" = "cpu=0" ]; then
  # suppression de la limite CPU (retour à l'état non contraint)
  K patch deploy/pricing-engine -n "$NS" --type=json \
    -p='[{"op":"remove","path":"/spec/template/spec/containers/0/resources/limits/cpu"}]' >/dev/null 2>&1 || true
else
  K set resources deploy/pricing-engine -n "$NS" --limits="$LIMIT" >/dev/null
fi
K rollout status deploy/pricing-engine -n "$NS" --timeout=180s
# laisser Beyla découvrir et instrumenter le nouveau processus
sleep 20
