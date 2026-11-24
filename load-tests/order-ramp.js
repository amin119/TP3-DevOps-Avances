// Scénario k6 — montée en charge progressive (paliers) jusqu'à 150 RPS.
// Sert à trouver le point d'inflexion (saturation CPU de pricing-engine).
//   k6 run -e MAX_RATE=150 -e STEP=25 -e HOLD=60s order-ramp.js
import http from 'k6/http';
import { check } from 'k6';
import { buildSummary } from './summary.js';

const TARGET = __ENV.TARGET || 'http://order-api.perf-lab.svc.cluster.local:8000';
const MAX_RATE = parseInt(__ENV.MAX_RATE || '150');
const STEP = parseInt(__ENV.STEP || '25');
const HOLD = __ENV.HOLD || '60s';
const LABEL = __ENV.LABEL || 'ramp';

// Paliers : 25 -> 50 -> ... -> 150 RPS (rampe de 10 s puis maintien HOLD)
const stages = [];
for (let r = STEP; r <= MAX_RATE; r += STEP) {
  stages.push({ target: r, duration: '10s' });
  stages.push({ target: r, duration: HOLD });
}

export const options = {
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  scenarios: {
    ramp_rps: {
      executor: 'ramping-arrival-rate',
      startRate: STEP,
      timeUnit: '1s',
      preAllocatedVUs: 150,
      maxVUs: 400,  // plafond volontaire : au-delà, k6 compte des itérations abandonnées
      stages,
    },
  },
};

export default function () {
  const payload = JSON.stringify({
    customer_id: `C-${__VU}-${__ITER}`,
    items: [{ sku: 'SKU-1001', quantity: 1 + (__ITER % 5) }],
  });
  const res = http.post(`${TARGET}/order`, payload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'POST /order' },
  });
  check(res, { 'status is 200': (r) => r.status === 200 });
}

export function handleSummary(data) {
  return buildSummary(data, LABEL);
}
