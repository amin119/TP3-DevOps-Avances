#!/usr/bin/env bash
# Installation complète du TP : cluster kind, images, Prometheus/Grafana, microservices, Beyla, dashboard.
# Usage : scripts/setup.sh
#   EXTRA_CA=/chemin/ca.crt  (optionnel) CA d'un proxy/antivirus TLS à faire confiance (build + nœud kind)
#   KUBECONFIG_INTERNAL=...  (optionnel) passe kubectl/helm par le conteneur toolbox (scripts/kt.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
K()    { if [ -n "${KUBECONFIG_INTERNAL:-}" ]; then scripts/kt.sh kubectl "$@"; else kubectl "$@"; fi; }
HELM() { if [ -n "${KUBECONFIG_INTERNAL:-}" ]; then scripts/kt.sh helm "$@"; else helm "$@"; fi; }

echo "== 1. Cluster kind"
kind get clusters 2>/dev/null | grep -qx perf-lab || kind create cluster --config k8s/kind-config.yaml
if [ -n "${KUBECONFIG_INTERNAL:-}" ]; then kind get kubeconfig --internal --name perf-lab > "$KUBECONFIG_INTERNAL"; fi
if [ -n "${EXTRA_CA:-}" ]; then
  docker cp "$EXTRA_CA" perf-lab-control-plane:/usr/local/share/ca-certificates/extra-ca.crt
  docker exec perf-lab-control-plane sh -c 'update-ca-certificates >/dev/null 2>&1 && systemctl restart containerd'
fi

echo "== 2. Images des microservices"
SECRET=(); [ -n "${EXTRA_CA:-}" ] && SECRET=(--secret "id=extraca,src=$EXTRA_CA")
docker build -q "${SECRET[@]}" -t order-api:1.0 services/order-api
docker build -q -t pricing-engine:1.0 services/pricing-engine
kind load docker-image order-api:1.0 pricing-engine:1.0 --name perf-lab

echo "== 3. Namespace + microservices"
K apply -f k8s/base/

echo "== 4. kube-prometheus-stack (Prometheus + Grafana)"
HELM repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
HELM repo update >/dev/null
HELM upgrade --install kps prometheus-community/kube-prometheus-stack --version 77.0.0 \
  -n perf-lab -f k8s/monitoring/kube-prometheus-stack-values.yaml --wait --timeout 10m

echo "== 5. Grafana Beyla (eBPF) + ServiceMonitor"
K apply -f k8s/beyla/beyla.yaml
K rollout status ds/beyla -n perf-lab --timeout=300s

echo "== 6. Tableau de bord Grafana"
K apply -f k8s/monitoring/grafana-dashboard-configmap.yaml

K rollout status deploy/order-api deploy/pricing-engine -n perf-lab --timeout=300s 2>/dev/null || true
K get pods -n perf-lab
echo "OK. Grafana : kubectl port-forward -n perf-lab svc/kps-grafana 3000:80  (admin/admin)"
