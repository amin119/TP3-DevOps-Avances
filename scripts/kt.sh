#!/usr/bin/env bash
# Exécute kubectl/helm depuis un conteneur "toolbox" attaché au réseau docker "kind".
# Utile quand un proxy/antivirus TLS intercepte l'accès à l'API server sur 127.0.0.1.
# Usage : scripts/kt.sh kubectl get pods -n perf-lab
#   KUBECONFIG_INTERNAL : chemin du kubeconfig interne (kind get kubeconfig --internal)
#   EXTRA_CA            : CA supplémentaire (optionnelle) pour les accès Internet de helm
ROOT="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)"
ARGS=(--rm -i --network kind -v "$ROOT:/work" -w /work -v "$KUBECONFIG_INTERNAL:/root/.kube/config:ro"
      -v kt-helm-cache:/root/.cache/helm -v kt-helm-config:/root/.config/helm)
[ -n "$EXTRA_CA" ] && ARGS+=(-v "$EXTRA_CA:/usr/local/share/ca-certificates/extra.crt:ro")
[ -n "$KT_PUBLISH" ] && ARGS+=(-p "$KT_PUBLISH")
[ -n "$KT_NAME" ] && ARGS+=(--name "$KT_NAME")
MSYS_NO_PATHCONV=1 exec docker run "${ARGS[@]}" alpine/k8s:1.33.1 sh -c 'update-ca-certificates >/dev/null 2>&1; exec "$@"' -- "$@"
