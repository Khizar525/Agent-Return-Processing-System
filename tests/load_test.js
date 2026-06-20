// Load Test — Agent 01 Customer Support System
// Owner: Member 5
//
// Simulates 1,000 concurrent tickets across 4 channels.
// Measures P95 resolution latency, error rate, and throughput.
//
// Usage:
//   k6 run --vus 1000 --duration 10m tests/load_test.js
//
// Environment variables:
//   BASE_URL         — FastAPI webhook URL (default: http://localhost:8000)
//   K6_API_TOKEN     — (optional) for k6 Cloud export

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

const channels = ['web_chat', 'email', 'whatsapp', 'sms'];

const resolutionTrend = new Trend('resolution_duration');
const errorRate = new Rate('error_rate');
const throughputCounter = new Counter('throughput');

export const options = {
  stages: [
    { duration: '1m', target: 250 },   // Ramp up to 250
    { duration: '2m', target: 500 },   // Ramp to 500
    { duration: '2m', target: 1000 },  // Ramp to 1000
    { duration: '3m', target: 1000 },  // Hold at 1000
    { duration: '1m', target: 500 },   // Ramp down
    { duration: '1m', target: 0 },     // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<30000'], // P95 < 30 seconds
    http_req_failed: ['rate<0.01'],      // Error rate < 1%
  },
};

function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomCustomerId() {
  return `CUST-${String(Math.floor(Math.random() * 10000)).padStart(4, '0')}`;
}

function randomOrderId() {
  return `ORD-${String(Math.floor(Math.random() * 5000)).padStart(4, '0')}`;
}

function randomMessage(channel) {
  const messages = {
    web_chat: [
      'I want to return my order',
      'Can I get a refund for',
      'My package arrived damaged',
      'I ordered the wrong size',
    ],
    email: [
      'I would like to request a return for order',
      'Please process a refund for my recent purchase',
      'I need a replacement for my damaged item',
    ],
    whatsapp: [
      'Hey, I need to return something',
      'Can you help me with a refund?',
      'My order is defective',
    ],
    sms: [
      'RETURN ORDER',
      'REFUND PLS',
      'WHERE IS MY PACKAGE',
    ],
  };
  const msg = randomChoice(messages[channel] || messages.web_chat);
  return `${msg} ${randomOrderId()}`;
}

export default function () {
  const channel = randomChoice(channels);
  const payload = JSON.stringify({
    customer_id: randomCustomerId(),
    channel: channel,
    raw_message: randomMessage(channel),
    session_id: null,
  });

  const startTime = Date.now();

  const res = http.post(`${BASE_URL}/webhook/message`, payload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '60s',
  });

  const duration = Date.now() - startTime;
  resolutionTrend.add(duration);
  throughputCounter.add(1);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response has session_id': (r) => {
      try {
        return JSON.parse(r.body).session_id !== undefined;
      } catch {
        return false;
      }
    },
    'response has resolution': (r) => {
      try {
        return typeof JSON.parse(r.body).resolution === 'string';
      } catch {
        return false;
      }
    },
    'response has agent_chain': (r) => {
      try {
        return Array.isArray(JSON.parse(r.body).agent_chain);
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);

  // Simulate think time between 500ms and 2s
  sleep(Math.random() * 1.5 + 0.5);
}
