#!/usr/bin/env node
/**
 * Phase 3.2 smoke checks — API URL + WSS derivation (no network required for URL tests).
 * Optional: LIVE=1 hits production health.
 */
const assert = require('assert');

function derive(http) {
  const base = http.replace(/\/$/, '');
  let ws;
  if (base.startsWith('https://')) ws = `wss://${base.slice(8)}`;
  else if (base.startsWith('http://')) ws = `ws://${base.slice(7)}`;
  else ws = base;
  return `${ws}/api/voice/session`;
}

assert.strictEqual(
  derive('https://cameroon-ai-tour-guide-api.onrender.com'),
  'wss://cameroon-ai-tour-guide-api.onrender.com/api/voice/session',
);
assert.strictEqual(
  derive('http://127.0.0.1:8000'),
  'ws://127.0.0.1:8000/api/voice/session',
);
console.log('OK url derivation');

async function live() {
  const api = process.env.NEXT_PUBLIC_API_URL || 'https://cameroon-ai-tour-guide-api.onrender.com';
  const res = await fetch(`${api.replace(/\/$/, '')}/api/health`);
  assert.strictEqual(res.status, 200);
  const body = await res.json();
  assert.ok(body.status);
  console.log('OK live health', body);
}

if (process.env.LIVE === '1') {
  live().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
