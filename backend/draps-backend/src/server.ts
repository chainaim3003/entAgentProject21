#!/usr/bin/env node
/**
 * DRAPS API Server
 * ================
 * Express server exposing the SWAPS / Hedge Advisor simulation endpoint.
 *
 * Only one functional route is registered here:
 *   POST /api/simulate   — runs the Postman collection through ACTUS,
 *                          returns A/B/C scenario totals to the caller.
 *
 * This server is consumed by the Hedge Advisor backend (entAgentProject21).
 * It is NOT a stablecoin / DeFi / vLEI server.
 */

import express from 'express';
import cors from 'cors';
import simulationRoutes from './routes/simulation.routes.js';

const app = express();
const PORT = 4000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

// The only route group this server exposes.
// simulation.routes.ts contains POST /api/simulate (config-based simulation).
app.use('/api', simulationRoutes);

// Lightweight health check — no external pings, just confirms the process is up.
app.get('/api/health', (_req, res) => {
  return res.json({
    status: 'healthy',
    service: 'DRAPS API Server',
    timestamp: new Date().toISOString(),
  });
});

app.listen(PORT, () => {
  console.error('\n🚀 DRAPS API Server');
  console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.error(`   Server:    http://localhost:${PORT}`);
  console.error(`   Health:    GET  http://localhost:${PORT}/api/health`);
  console.error(`   Simulate:  POST http://localhost:${PORT}/api/simulate`);
  console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
});
