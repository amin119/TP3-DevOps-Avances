# TP DevOps & eBPF — Indicateurs RED sur une chaîne de microservices

Mesure des indicateurs **RED** (Rate, Errors, Duration) sur la chaîne
`k6 → order-api (A) → pricing-engine (B)`, collectés **uniquement par eBPF**
(Grafana Beyla) : aucun SDK de télémétrie dans le code des services.

```
Client (k6) ──▶ [ order-api : FastAPI ]  ──HTTP──▶ [ pricing-engine : Go ]
                    POST /order                       GET /price
        ▲ kprobes (sockets)                ▲ uprobes (net/http)
        └──────────── Grafana Beyla (DaemonSet eBPF) ──▶ :9090/metrics ──▶ Prometheus ──▶ Grafana
```

## Arborescence

| Chemin | Contenu |
|---|---|
| `services/order-api/` | Service A — Python FastAPI + httpx (aucune lib d'observabilité) |
| `services/pricing-engine/` | Service B — Go `net/http`, injection CPU / latence / erreurs par variables d'env |
| `k8s/kind-config.yaml` | Cluster kind mono-nœud `perf-lab` |
| `k8s/base/` | Namespace `perf-lab`, Deployments + Services ClusterIP de A et B |
| `k8s/monitoring/` | Valeurs Helm `kube-prometheus-stack` (config minimale) + ConfigMap du dashboard |
| `k8s/beyla/beyla.yaml` | DaemonSet Beyla (capacités BPF, SYS_PTRACE, NET_ADMIN…), RBAC, ConfigMap, Service, ServiceMonitor |
| `k8s/k6/k6-job.yaml` | Job k6 exécuté dans le cluster |
| `load-tests/` | Scénarios k6 : `order-constant.js` (50 RPS / 3 min), `order-ramp.js` (paliers → 150 RPS) |
| `grafana/perf-lab-red-dashboard.json` | Export JSON du tableau de bord Grafana |
| `scripts/` | Installation, scénarios, tirs, extraction des métriques, génération du dashboard |
| `results/` | Résumés k6 et métriques eBPF extraites de Prometheus pour chaque régime |
| `report/` | Rapport d'analyse LaTeX (`rapport.tex`) + figures et captures |

## Variables d'injection de fautes (pricing-engine)

| Variable | Effet |
|---|---|
| `BASE_LATENCY_MS` | latence de traitement normale |
| `JITTER_MS` | latence aléatoire uniforme ajoutée `[0, JITTER]` |
| `SLOW_PERCENT` / `SLOW_LATENCY_MS` | % de requêtes lentes et leur latence (tail latency) |
| `ERROR_RATE` | % de réponses HTTP 500 |
| `CPU_ITERATIONS` | itérations SHA-256 par requête (charge CPU, ~0,19 µs / itération) |

## Démarrage rapide

Prérequis : Linux / WSL2 avec noyau ≥ 5.15 et BTF (`/sys/kernel/btf/vmlinux`), `docker`, `kind`, `kubectl`, `helm`.

```bash
scripts/setup.sh                         # cluster + stack + services + Beyla + dashboard
kubectl port-forward -n perf-lab svc/kps-grafana 3000:80 &                         # Grafana (admin/admin)
kubectl port-forward -n perf-lab svc/kps-kube-prometheus-stack-prometheus 9091:9090 &
scripts/run-all.sh                       # 4 régimes : nominal, errors, tail, saturation
```

Commandes unitaires :

```bash
scripts/scenario.sh tail                              # reconfigure pricing-engine
scripts/run-load.sh tail order-constant.js 50 3m      # tir k6 (Job dans le cluster)
python scripts/extract_metrics.py tail 170            # métriques eBPF depuis Prometheus
python scripts/gen_dashboard.py                       # régénère le JSON du dashboard
```

Validation de la chaîne :

```bash
kubectl run curl -n perf-lab --rm -i --restart=Never --image=curlimages/curl:8.14.1 -- \
  curl -s -X POST http://order-api:8000/order -H 'Content-Type: application/json' \
  -d '{"customer_id":"C-42","items":[{"sku":"SKU-1001","quantity":3}]}'
```

## Remarques d'environnement (Windows + Docker Desktop / WSL2)

* **Version de Beyla et noyau** : Beyla ≥ 2.6 attache une kprobe sur le hook LSM
  `security_socket_accept`. L'ancien noyau WSL2 5.15 est compilé sans
  `CONFIG_SECURITY_NETWORK`, ce symbole n'existe donc pas et l'instrumentation des processus
  non-Go (Python) échoue. Sur ce noyau, utiliser `grafana/beyla:2.5.8`. Avec le noyau
  WSL2 6.18 (utilisé pour les mesures), `grafana/beyla:3.42.0` fonctionne.
* **Proxy / antivirus TLS** (ex. bouclier Web d'Avast) : si l'HTTPS est intercepté, exporter la CA
  racine et lancer `EXTRA_CA=ca.crt scripts/setup.sh` (la CA est passée au build en *secret*
  BuildKit et installée dans le nœud kind). Si l'accès à l'API server `127.0.0.1` est lui aussi
  intercepté, utiliser `KUBECONFIG_INTERNAL=... scripts/...` : kubectl/helm s'exécutent alors
  dans un conteneur sur le réseau docker `kind` (`scripts/kt.sh`).
