"""Extrait de Prometheus les indicateurs RED (mesurés par eBPF) d'un tir k6.

Usage : python scripts/extract_metrics.py <label> [duree_s] [--steps N:HOLD]
  - lit results/<label>-window.json (écrit par run-load.sh)
  - écrit results/<label>-prom.json
Prometheus doit être joignable sur PROM_URL (défaut http://127.0.0.1:9091).
"""
import json
import os
import sys
import urllib.parse
import urllib.request

PROM = os.getenv("PROM_URL", "http://127.0.0.1:9091")
NS = 'namespace="perf-lab"'
SEL = {
    "order-api (serveur)": ("http_server_request_duration_seconds", f'{NS},service_name="order-api",http_route="/order"'),
    "A→B (client)": ("http_client_request_duration_seconds", f'{NS},service_name="order-api"'),
    "pricing-engine (serveur)": ("http_server_request_duration_seconds", f'{NS},service_name="pricing-engine",http_route="/price"'),
}


def query(expr, t):
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": t})
    with urllib.request.urlopen(url, timeout=30) as r:
        res = json.load(r)["data"]["result"]
    return float(res[0]["value"][1]) if res else 0.0


def red(metric, sel, end, dur):
    w = f"[{dur}s]"
    cnt = f"sum(rate({metric}_count{{{sel}}}{w}))"
    out = {
        "rps": query(cnt, end),
        "avg_ms": 1000 * query(f"sum(rate({metric}_sum{{{sel}}}{w})) / {cnt}", end),
        "err_pct": 100 * query(
            f'(sum(rate({metric}_count{{{sel},http_response_status_code=~"5.."}}{w})) or vector(0)) / {cnt}', end),
    }
    for p in (0.5, 0.95, 0.99):
        out[f"p{int(p * 100)}_ms"] = 1000 * query(
            f"histogram_quantile({p}, sum(rate({metric}_bucket{{{sel}}}{w})) by (le))", end)
    return {k: round(v, 2) for k, v in out.items()}


def cpu(end, dur):
    sel = f'{NS},container="pricing-engine"'
    w = f"[{dur}s]"
    return {
        "cpu_cores": round(query(f"sum(rate(container_cpu_usage_seconds_total{{{sel}}}{w}))", end), 3),
        "throttled_pct": round(100 * query(
            f"sum(rate(container_cpu_cfs_throttled_periods_total{{{sel}}}{w})) / "
            f"sum(rate(container_cpu_cfs_periods_total{{{sel}}}{w}))", end), 1),
    }


def traffic_window(win):
    """Fenêtre réelle du trafic (le pod k6 démarre quelques secondes après le Job) :
    premier et dernier instant où order-api reçoit plus de 3 req/s."""
    q = (f'sum(rate(http_server_request_duration_seconds_count{{{SEL["order-api (serveur)"][1]}}}[10s]))')
    url = f"{PROM}/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": q, "start": win["start"], "end": win["end"] + 60, "step": 2})
    with urllib.request.urlopen(url, timeout=30) as r:
        vals = json.load(r)["data"]["result"][0]["values"]
    active = [int(t) for t, v in vals if float(v) > 3]
    return active[0] - 5, active[-1] - 5       # compensation du retard de rate[10s]


def main():
    label = sys.argv[1]
    win = json.load(open(f"results/{label}-window.json", encoding="utf-8"))
    t_start, t_end = traffic_window(win)
    result = {"label": label, "window": win, "traffic": {"start": t_start, "end": t_end}}
    steps = next((a.split(":", 1)[1] for a in sys.argv[2:] if a.startswith("--steps")), None)
    if steps is None:
        dur = t_end - t_start
        end = t_end
        result["duration_s"] = dur
        result["services"] = {name: red(m, s, end, dur) for name, (m, s) in SEL.items()}
        result["cpu"] = cpu(end, dur)
    else:
        # Tir en paliers : n paliers de (10 s de rampe + HOLD s de maintien), durées k6.
        # L'horloge murale de la VM peut dériver par rapport à k6 : on répartit
        # la durée réelle observée proportionnellement entre les paliers.
        n, hold = (int(x) for x in steps.split("x"))
        step_len = (t_end - t_start) / n
        result["steps"] = []
        for i in range(n):
            end = int(t_start + (i + 1) * step_len) - 2
            dur = int(step_len * hold / (10 + hold)) - 12   # on ignore le début du palier (transitoire)
            result["steps"].append({
                "target_rps": (i + 1) * 25,
                "services": {name: red(m, s, end, dur) for name, (m, s) in SEL.items()},
                "cpu": cpu(end, dur),
            })
    path = f"results/{label}-prom.json"
    json.dump(result, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
