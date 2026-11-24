"""Génère le tableau de bord Grafana RED (eBPF / Beyla) du TP au format JSON.

Usage : python scripts/gen_dashboard.py  ->  grafana/perf-lab-red-dashboard.json
"""
import json
import pathlib

DS = {"type": "prometheus", "uid": "prometheus"}
NS = 'namespace="perf-lab"'
SA = f'{NS},service_name="order-api",http_route="/order"'        # serveur A
SB = f'{NS},service_name="pricing-engine",http_route="/price"'   # serveur B
CA = f'{NS},service_name="order-api"'                            # client A -> B
SRV = "http_server_request_duration_seconds"
CLI = "http_client_request_duration_seconds"
W = "[1m]"

_id = 0


def nid():
    global _id
    _id += 1
    return _id


def tgt(expr, legend, ref="A", instant=False):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t.update({"instant": True, "range": False})
    return t


def q(p, sel, metric=SRV, win=W):
    return f"histogram_quantile({p}, sum(rate({metric}_bucket{{{sel}}}{win})) by (le))"


def mean(sel, metric=SRV, win=W):
    return f"sum(rate({metric}_sum{{{sel}}}{win})) / sum(rate({metric}_count{{{sel}}}{win}))"


def row(title, y):
    return {"type": "row", "title": title, "id": nid(), "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


def ts(title, targets, x, y, w=12, h=8, unit="s", desc="", stack=False, overrides=None, minv=None):
    p = {
        "type": "timeseries", "title": title, "id": nid(), "datasource": DS, "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {"lineWidth": 2, "fillOpacity": 25 if stack else 8, "showPoints": "never",
                           "stacking": {"mode": "normal" if stack else "none", "group": "A"}},
            },
            "overrides": overrides or [],
        },
        "options": {"legend": {"displayMode": "table", "placement": "bottom",
                               "calcs": ["mean", "max", "lastNotNull"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }
    if minv is not None:
        p["fieldConfig"]["defaults"]["min"] = minv
    return p


def stat(title, expr, x, y, w=4, h=4, unit="s", desc="", color="blue", decimals=None):
    p = {
        "type": "stat", "title": title, "id": nid(), "datasource": DS, "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "targets": [tgt(expr, title, instant=True)],
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "fixed", "fixedColor": color},
                                     "thresholds": {"mode": "absolute", "steps": [{"color": color, "value": None}]}},
                        "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": "background", "graphMode": "none", "textMode": "value",
                    "justifyMode": "center"},
    }
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p


def color_override(name, color):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]}


R = "[$__range]"   # statistiques calculées sur toute la fenêtre affichée (= durée du tir)
panels = []
y = 0

# ---------------- Synthèse ----------------
panels.append(row("Synthèse du tir (calculée sur la plage de temps sélectionnée)", y)); y += 1
panels += [
    stat("order-api · RPS", f"sum(rate({SRV}_count{{{SA}}}{R}))", 0, y, unit="reqps", color="purple", decimals=1),
    stat("order-api · moyenne", mean(SA, win=R), 4, y, color="blue"),
    stat("order-api · p50", q(0.50, SA, win=R), 8, y, color="green"),
    stat("order-api · p95", q(0.95, SA, win=R), 12, y, color="orange"),
    stat("order-api · p99", q(0.99, SA, win=R), 16, y, color="red"),
    stat("order-api · % erreurs 5xx",
         f'100 * (sum(rate({SRV}_count{{{SA},http_response_status_code=~"5.."}}{R})) or vector(0)) '
         f"/ sum(rate({SRV}_count{{{SA}}}{R}))", 20, y, unit="percent", color="dark-red", decimals=2),
]
y += 4
panels += [
    stat("pricing-engine · RPS", f"sum(rate({SRV}_count{{{SB}}}{R}))", 0, y, unit="reqps", color="purple", decimals=1),
    stat("pricing-engine · moyenne", mean(SB, win=R), 4, y, color="blue"),
    stat("pricing-engine · p50", q(0.50, SB, win=R), 8, y, color="green"),
    stat("pricing-engine · p95", q(0.95, SB, win=R), 12, y, color="orange"),
    stat("pricing-engine · p99", q(0.99, SB, win=R), 16, y, color="red"),
    stat("pricing-engine · % erreurs 5xx",
         f'100 * (sum(rate({SRV}_count{{{SB},http_response_status_code=~"5.."}}{R})) or vector(0)) '
         f"/ sum(rate({SRV}_count{{{SB}}}{R}))", 20, y, unit="percent", color="dark-red", decimals=2),
]
y += 4

# ---------------- Rate ----------------
panels.append(row("R — Rate : débit par service", y)); y += 1
panels.append(ts(
    "Débit entrant par service (requêtes/s)",
    [tgt(f'sum(rate({SRV}_count{{{NS},http_route!="/health"}}{W})) by (service_name)', "{{service_name}}")],
    0, y, unit="reqps", minv=0,
    desc="sum(rate(http_server_request_duration_seconds_count{namespace=\"perf-lab\"}[1m])) by (service_name) "
         "— les sondes de readiness (/health) sont exclues."))
panels.append(ts(
    "Appels A → B : émis par order-api (client) vs reçus par pricing-engine (serveur)",
    [tgt(f"sum(rate({CLI}_count{{{CA}}}{W}))", "émis par order-api (client eBPF)", "A"),
     tgt(f"sum(rate({SRV}_count{{{SB}}}{W}))", "reçus par pricing-engine (serveur eBPF)", "B")],
    12, y, unit="reqps", minv=0,
    desc="Les deux courbes doivent se superposer : chaque requête POST /order génère exactement un GET /price."))
y += 8

# ---------------- Errors ----------------
panels.append(row("E — Errors : taux et propagation des erreurs", y)); y += 1
panels.append(ts(
    "Taux d'erreurs 5xx côté serveur, par service (%)",
    [tgt(f'100 * (sum(rate({SRV}_count{{{NS},http_route!="/health",http_response_status_code=~"5.."}}{W})) by (service_name)) '
         f'/ sum(rate({SRV}_count{{{NS},http_route!="/health"}}{W})) by (service_name)', "{{service_name}} (serveur)", "A"),
     tgt(f'100 * (sum(rate({CLI}_count{{{CA},http_response_status_code=~"5.."}}{W}))) '
         f"/ sum(rate({CLI}_count{{{CA}}}{W}))", "order-api → pricing-engine (vu par le client)", "B")],
    0, y, unit="percent", minv=0,
    desc="Si l'erreur apparaît côté serveur B ET côté client A→B, le service fautif est pricing-engine."))
panels.append(ts(
    "Réponses par code HTTP et par service (req/s)",
    [tgt(f'sum(rate({SRV}_count{{{NS},http_route!="/health"}}{W})) by (service_name, http_response_status_code)',
         "{{service_name}} · {{http_response_status_code}}", "A"),
     tgt(f"sum(rate({CLI}_count{{{CA}}}{W})) by (http_response_status_code)",
         "client A→B · {{http_response_status_code}}", "B")],
    12, y, unit="reqps", stack=False, minv=0))
y += 8

# ---------------- Duration ----------------
panels.append(row("D — Duration : percentiles de latence", y)); y += 1
lat_over = [color_override("p50", "green"), color_override("p95", "orange"),
            color_override("p99", "red"), color_override("moyenne", "blue")]
panels.append(ts(
    "order-api (POST /order) — p50 / p95 / p99 / moyenne",
    [tgt(q(0.50, SA), "p50", "A"), tgt(q(0.95, SA), "p95", "B"), tgt(q(0.99, SA), "p99", "C"),
     tgt(mean(SA), "moyenne", "D")], 0, y, overrides=lat_over, minv=0,
    desc="histogram_quantile(0.99, sum(rate(http_server_request_duration_seconds_bucket{service_name=\"order-api\"}[1m])) by (le))"))
panels.append(ts(
    "pricing-engine (GET /price) — p50 / p95 / p99 / moyenne",
    [tgt(q(0.50, SB), "p50", "A"), tgt(q(0.95, SB), "p95", "B"), tgt(q(0.99, SB), "p99", "C"),
     tgt(mean(SB), "moyenne", "D")], 12, y, overrides=lat_over, minv=0))
y += 8
panels.append({
    "type": "heatmap", "title": "order-api — distribution des latences (heatmap des buckets eBPF)", "id": nid(),
    "datasource": DS, "gridPos": {"h": 8, "w": 24, "x": 0, "y": y},
    "targets": [{"datasource": DS, "expr": f"sum(increase({SRV}_bucket{{{SA}}}[$__rate_interval])) by (le)",
                 "legendFormat": "{{le}}", "format": "heatmap", "refId": "A"}],
    "options": {"calculate": False, "yAxis": {"unit": "s"}, "color": {"scheme": "Oranges", "mode": "scheme"},
                "cellGap": 1, "tooltip": {"show": True, "yHistogram": True}},
})
y += 8

# ---------------- Décomposition ----------------
panels.append(row("Décomposition de la latence : T_interne(A) = T_serveur(A) − T_client(A→B)", y)); y += 1
dec_over = [color_override("T_serveur(A)", "blue"), color_override("T_client(A→B)", "purple"),
            color_override("T_interne(A)", "yellow")]
panels.append(ts(
    "Latence moyenne : serveur A, client A→B et temps interne de A",
    [tgt(mean(SA), "T_serveur(A)", "A"), tgt(mean(CA, CLI), "T_client(A→B)", "B"),
     tgt(f"({mean(SA)}) - ({mean(CA, CLI)})", "T_interne(A)", "C")], 0, y, w=12, overrides=dec_over, minv=0,
    desc="La moyenne est additive : la soustraction des moyennes est exacte (contrairement aux percentiles)."))
panels.append(ts(
    "Part de la latence de A (empilé) : attente de B vs traitement interne",
    [tgt(mean(CA, CLI), "T_client(A→B)", "A"),
     tgt(f"({mean(SA)}) - ({mean(CA, CLI)})", "T_interne(A)", "B")], 12, y, w=12, stack=True,
    overrides=dec_over, minv=0))
y += 8
panels += [
    stat("T_serveur(A) moyen", mean(SA, win=R), 0, y, w=6, color="blue"),
    stat("T_client(A→B) moyen", mean(CA, CLI, win=R), 6, y, w=6, color="purple"),
    stat("T_interne(A) moyen", f"({mean(SA, win=R)}) - ({mean(CA, CLI, win=R)})", 12, y, w=6, color="yellow"),
    stat("Part de B dans la latence de A", f"100 * ({mean(CA, CLI, win=R)}) / ({mean(SA, win=R)})",
         18, y, w=6, unit="percent", color="dark-purple", decimals=1),
]
y += 4

# ---------------- Saturation ----------------
panels.append(row("Saturation CPU et loi de Little", y)); y += 1
CPU_SEL = f'{NS},container="pricing-engine"'
panels.append(ts(
    "pricing-engine — CPU consommé vs limite (cœurs)",
    [tgt(f"sum(rate(container_cpu_usage_seconds_total{{{CPU_SEL}}}{W}))", "CPU utilisé", "A"),
     tgt(f'sum(container_spec_cpu_quota{{{CPU_SEL}}} / container_spec_cpu_period{{{CPU_SEL}}})', "limite (quota CFS)", "B")],
    0, y, w=12, unit="short", minv=0,
    overrides=[color_override("limite (quota CFS)", "red")]))
panels.append(ts(
    "pricing-engine — throttling CFS (% des périodes bridées)",
    [tgt(f"100 * sum(rate(container_cpu_cfs_throttled_periods_total{{{CPU_SEL}}}{W})) "
         f"/ sum(rate(container_cpu_cfs_periods_total{{{CPU_SEL}}}{W}))", "périodes throttlées", "A")],
    12, y, w=12, unit="percent", minv=0))
y += 8
panels.append(ts(
    "Point d'inflexion : débit de B (axe gauche) vs latence p99 de A (axe droit)",
    [tgt(f"sum(rate({SRV}_count{{{SB}}}{W}))", "débit pricing-engine (req/s)", "A"),
     tgt(f"sum(rate({SRV}_count{{{SA}}}{W}))", "débit order-api (req/s)", "B"),
     tgt(q(0.99, SA), "p99 order-api", "C"), tgt(q(0.50, SA), "p50 order-api", "D")],
    0, y, w=12, unit="reqps", minv=0,
    overrides=[{"matcher": {"id": "byRegexp", "options": "^p.. order-api$"},
                "properties": [{"id": "unit", "value": "s"}, {"id": "custom.axisPlacement", "value": "right"},
                               {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 10]}}]}]))
panels.append(ts(
    "Loi de Little : L = λ × W (requêtes simultanément en cours)",
    [tgt(f'sum(rate({SRV}_sum{{{NS},http_route!="/health"}}{W})) by (service_name)', "L = λ·W · {{service_name}}")],
    12, y, w=12, unit="short", minv=0,
    desc="rate(somme des durées) = λ × W moyen = nombre moyen de requêtes en cours dans le service."))
y += 8

dashboard = {
    "uid": "perf-lab-red",
    "title": "TP eBPF — RED order-api → pricing-engine",
    "tags": ["ebpf", "beyla", "red", "perf-lab"],
    "timezone": "browser",
    "schemaVersion": 41,
    "version": 1,
    "refresh": "",
    "time": {"from": "now-15m", "to": "now"},
    "graphTooltip": 1,
    "panels": panels,
    "templating": {"list": []},
    "annotations": {"list": []},
}

out = pathlib.Path(__file__).resolve().parent.parent / "grafana" / "perf-lab-red-dashboard.json"
out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{out} : {len(panels)} panneaux")
