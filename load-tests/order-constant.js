// Scénario k6 — trafic constant (open model) sur POST /order de order-api.
// Par défaut : 50 requêtes/seconde pendant 3 minutes.
//   k6 run -e RATE=50 -e DURATION=3m -e TARGET=http://order-api.perf-lab:8000 order-constant.js
import http from 'k6/http';
import { check } from 'k6';
import { buildSummary } from './summary.js';

const TARGET = __ENV.TARGET || 'http://order-api.perf-lab.svc.cluster.local:8000';
const RATE = parseInt(__ENV.RATE || '50');
const DURATION = __ENV.DURATION || '3m';
const LABEL = __ENV.LABEL || 'constant';

export const options = {
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  scenarios: {
    constant_rps: {
      // constant-arrival-rate : le débit est imposé, indépendamment de la latence
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 100,
      maxVUs: 600,
    },
  },
};

const SKUS = ['SKU-1001', 'SKU-2002', 'SKU-3003', 'SKU-4004'];

export default function () {
  const payload = JSON.stringify({
    customer_id: `C-${__VU}-${__ITER}`,
    items: [
      { sku: SKUS[__ITER % SKUS.length], quantity: 1 + (__ITER % 5) },
      { sku: 'SKU-9999', quantity: 1 },
    ],
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
