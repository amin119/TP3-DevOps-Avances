// Résumé k6 compact (texte + JSON) : RPS, moyenne, p50, p95, p99, % erreurs.
function fmt(ms) {
  return ms === undefined ? 'n/a' : `${ms.toFixed(2)} ms`;
}

export function buildSummary(data, label) {
  const d = data.metrics.http_req_duration.values;
  const reqs = data.metrics.http_reqs.values;
  const failed = data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : 0;
  const dropped = data.metrics.dropped_iterations ? data.metrics.dropped_iterations.values.count : 0;

  const out = {
    scenario: label,
    requests: reqs.count,
    rps: +reqs.rate.toFixed(2),
    avg_ms: +d.avg.toFixed(2),
    p50_ms: +d.med.toFixed(2),
    p90_ms: +d['p(90)'].toFixed(2),
    p95_ms: +d['p(95)'].toFixed(2),
    p99_ms: +d['p(99)'].toFixed(2),
    max_ms: +d.max.toFixed(2),
    error_pct: +(failed * 100).toFixed(2),
    dropped_iterations: dropped,
  };

  const text = [
    '',
    `================ k6 — scénario « ${label} » ================`,
    `  requêtes        : ${out.requests}`,
    `  débit (RPS)     : ${out.rps}`,
    `  moyenne         : ${fmt(d.avg)}`,
    `  p50 (médiane)   : ${fmt(d.med)}`,
    `  p90             : ${fmt(d['p(90)'])}`,
    `  p95             : ${fmt(d['p(95)'])}`,
    `  p99             : ${fmt(d['p(99)'])}`,
    `  max             : ${fmt(d.max)}`,
    `  erreurs HTTP    : ${out.error_pct} %`,
    `  itér. abandonnées: ${dropped}`,
    '==============================================================',
    `K6_SUMMARY_JSON ${JSON.stringify(out)}`,
    '',
  ].join('\n');

  return { stdout: text };
}
