/**
 * Claude.ai GET Routes
 * ====================
 * These routes enable claude.ai (browser) to trigger portfolio verification
 * and DeFi simulation via simple GET URLs using web_fetch.
 * 
 * claude.ai's web_fetch can only do GET requests — it cannot send POST bodies.
 * These routes accept all parameters in the URL path/query string.
 * 
 * Endpoints:
 *   GET /api/claude/verify/:filename                    — verify portfolio with default US GENIUS thresholds
 *   GET /api/claude/verify/:filename/:jurisdiction      — verify with specific jurisdiction (eu-mica, us-genius)
 *   GET /api/claude/simulate/:category/:filename        — run a stablecoin stimulation
 *   GET /api/claude/defi-simulations                    — list all DeFi simulation files
 *   GET /api/claude/defi-simulate/:category/:filename   — run a DeFi simulation collection
 */

import { Router } from 'express';
import type { Request, Response } from 'express';
import { StableCoinVerifier } from '../verifier/StableCoinVerifier.js';
import type { VerificationParams, PortfolioConfig } from '../types/index.js';
import { runStimulation, ENVIRONMENTS } from '../api/SimulationRunner.js';

const router = Router();

const DEFAULT_ACTUS_URL = process.env.ACTUS_URL || 'http://localhost:8083/eventsBatch';
const DEFAULT_RISK_URL = process.env.RISK_URL || 'http://localhost:8082';
const DEFAULT_SIM_URL = process.env.SIM_URL || 'http://localhost:8083';

const THRESHOLDS: Record<string, any> = {
  'eu-mica': { backingRatio: 100, liquidityRatio: 30, concentrationLimit: 60, assetQuality: 85 },
  'us-genius': { backingRatio: 100, liquidityRatio: 20, concentrationLimit: 40, assetQuality: 80 },
  'custom': { backingRatio: 100, liquidityRatio: 20, concentrationLimit: 40, assetQuality: 80 },
};

// ─── GET /api/claude/verify/:filename/:jurisdiction? ─────────────────────────
router.get('/claude/verify/:filename/:jurisdiction?', async (req: Request, res: Response) => {
  try {
    const fs = await import('fs');
    const path = await import('path');
    const os = await import('os');
    const { fileURLToPath } = await import('url');
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);

    const filename = req.params.filename.endsWith('.json') ? req.params.filename : `${req.params.filename}.json`;
    const jurisdiction = req.params.jurisdiction || 'us-genius';
    const thresholds = THRESHOLDS[jurisdiction] || THRESHOLDS['us-genius'];

    const configPath = path.join(__dirname, '..', '..', 'config');
    let filePath = path.join(configPath, filename);
    if (!fs.existsSync(filePath)) filePath = path.join(configPath, 'test-scenarios', filename);

    if (!fs.existsSync(filePath)) {
      return res.status(404).json({
        error: `Portfolio file not found: ${filename}`,
        available_portfolios: fs.existsSync(configPath) ? fs.readdirSync(configPath).filter((f: string) => f.startsWith('portfolio-') && f.endsWith('.json')) : [],
        available_scenarios: fs.existsSync(path.join(configPath, 'test-scenarios')) ? fs.readdirSync(path.join(configPath, 'test-scenarios')).filter((f: string) => f.endsWith('.json')) : [],
      });
    }

    const portfolioData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    const portfolioConfig: PortfolioConfig = {
      portfolioMetadata: { portfolioId: portfolioData.portfolioMetadata?.portfolioId || filename.replace('.json', ''), totalNotional: portfolioData.portfolioMetadata?.totalNotional || 0, currency: portfolioData.portfolioMetadata?.currency || 'USD' },
      contracts: portfolioData.contracts || [],
    };

    if (portfolioConfig.contracts.length === 0) return res.status(400).json({ error: 'Portfolio contains no contracts' });

    const tempPath = path.join(os.tmpdir(), `claude-ai-verify-${Date.now()}.json`);
    fs.writeFileSync(tempPath, JSON.stringify(portfolioConfig, null, 2));

    const params: VerificationParams = { backingRatioThreshold: thresholds.backingRatio, liquidityRatioThreshold: thresholds.liquidityRatio, concentrationLimit: thresholds.concentrationLimit, qualityThreshold: thresholds.assetQuality, actusUrl: DEFAULT_ACTUS_URL, portfolioPath: tempPath };

    console.error(`\n🌐 Claude.ai Verify: ${filename} (${jurisdiction})`);
    const verifier = new StableCoinVerifier();
    const result = await verifier.verify(params);
    try { fs.unlinkSync(tempPath); } catch { }

    return res.json({
      source: 'live_actus_server', actus_url: DEFAULT_ACTUS_URL, portfolio_file: filename, jurisdiction, thresholds_used: thresholds,
      compliant: result.compliant, overall_status: result.summary.overallStatus, periods_analyzed: result.summary.periodsAnalyzed,
      metrics: {
        backing_ratio: { value: result.riskMetrics.averageBackingRatio, threshold: thresholds.backingRatio, status: result.summary.backing.status },
        liquidity_ratio: { value: result.riskMetrics.averageLiquidityRatio, threshold: thresholds.liquidityRatio, status: result.summary.liquidity.status },
        concentration_risk: { value: result.riskMetrics.maxConcentrationRisk, limit: thresholds.concentrationLimit, status: result.summary.concentration.status },
        asset_quality: { value: result.riskMetrics.averageAssetQuality, threshold: thresholds.assetQuality, status: result.summary.quality.status },
      },
      failure_reasons: result.summary.failureReasons, timestamp: result.timestamp,
    });
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

// ─── GET /api/claude/simulate/:category/:filename ────────────────────────────
router.get('/claude/simulate/:category/:filename', async (req: Request, res: Response) => {
  try {
    const fs = await import('fs');
    const path = await import('path');
    const { fileURLToPath } = await import('url');
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);

    const stimulationId = `${req.params.category}/${req.params.filename}`;
    const filePath = path.join(__dirname, '..', '..', 'config', 'stimulation', `${stimulationId}.json`);

    if (!fs.existsSync(filePath)) return res.status(404).json({ error: `Stimulation file not found: ${stimulationId}.json` });

    const collectionJson = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    console.error(`\n🌐 Claude.ai Simulate: ${stimulationId}`);

    const result = await runStimulation(collectionJson, ENVIRONMENTS.localhost, 'localhost');
    return res.json({ source: 'live_actus_server', stimulation_id: stimulationId, ...result });
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

// ─── GET /api/claude/defi-simulations ────────────────────────────────────────
router.get('/claude/defi-simulations', async (_req: Request, res: Response) => {
  try {
    const fs = await import('fs');
    const path = await import('path');
    const { fileURLToPath } = await import('url');
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);
    const stimPath = path.join(__dirname, '..', '..', 'config', 'stimulation', 'defi-liquidation-collateral');

    const result: Record<string, string[]> = {};
    if (fs.existsSync(stimPath)) {
      for (const d of fs.readdirSync(stimPath)) {
        if (fs.statSync(path.join(stimPath, d)).isDirectory()) {
          const files = fs.readdirSync(path.join(stimPath, d)).filter((f: string) => f.endsWith('.json'));
          if (files.length > 0) result[d] = files;
        }
      }
    }
    return res.json({ source: 'filesystem', categories: result, usage: 'GET /api/claude/defi-simulate/:category/:filename' });
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

// ─── GET /api/claude/defi-simulate/:category/:filename ───────────────────────
router.get('/claude/defi-simulate/:category/:filename', async (req: Request, res: Response) => {
  try {
    const fs = await import('fs');
    const path = await import('path');
    const axios = (await import('axios')).default;
    const { fileURLToPath } = await import('url');
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);

    const category = req.params.category;
    const filename = req.params.filename.endsWith('.json') ? req.params.filename : `${req.params.filename}.json`;
    const filePath = path.join(__dirname, '..', '..', 'config', 'stimulation', 'defi-liquidation-collateral', category, filename);

    if (!fs.existsSync(filePath)) return res.status(404).json({ error: `Not found: ${category}/${filename}`, hint: 'GET /api/claude/defi-simulations' });

    const collectionJson = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    console.error(`\n🌐 Claude.ai DeFi Simulate: ${category}/${filename}`);

    const riskUrl = DEFAULT_RISK_URL;
    const simUrl = DEFAULT_SIM_URL;
    const items = collectionJson.item || [];
    const loadResults: any = { reference_indexes: [], prepayment_models: [], ltv_models: [], scenario: null };

    for (const item of items) {
      const raw = item.request?.body?.raw;
      if (!raw) continue;
      let body: any;
      try { body = JSON.parse(raw); } catch { continue; }
      const urlPath = item.request?.url?.path?.join('/') || '';

      if (urlPath.includes('addReferenceIndex')) {
        try {
          const resp = await axios.post(`${riskUrl}/addReferenceIndex`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 30000 });
          loadResults.reference_indexes.push({ riskFactorID: body.riskFactorID, marketObjectCode: body.marketObjectCode, data_points: body.data?.length || 0, status: 'loaded', server_response: typeof resp.data === 'string' ? resp.data.trim() : resp.data });
        } catch (err: any) { loadResults.reference_indexes.push({ riskFactorID: body.riskFactorID, status: 'error', error: err.message }); }
      } else if (urlPath.includes('addTwoDimensionalPrepaymentModel')) {
        try {
          const resp = await axios.post(`${riskUrl}/addTwoDimensionalPrepaymentModel`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 30000 });
          loadResults.prepayment_models.push({ riskFactorId: body.riskFactorId, evaluation_times: body.prepaymentEventTimes?.length || 0, status: 'loaded', server_response: typeof resp.data === 'string' ? resp.data.trim() : resp.data });
        } catch (err: any) { loadResults.prepayment_models.push({ riskFactorId: body.riskFactorId, status: 'error', error: err.message }); }
      } else if (urlPath.includes('addBufferLTVModel')) {
        try {
          const resp = await axios.post(`${riskUrl}/addBufferLTVModel`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 30000 });
          loadResults.ltv_models.push({ riskFactorId: body.riskFactorId, type: 'BufferLTVModel', status: 'loaded', server_response: typeof resp.data === 'string' ? resp.data.trim() : resp.data });
        } catch (err: any) { loadResults.ltv_models.push({ riskFactorId: body.riskFactorId, type: 'BufferLTVModel', status: 'error', error: err.message }); }
      } else if (urlPath.includes('addCollateralLTVModel')) {
        try {
          const resp = await axios.post(`${riskUrl}/addCollateralLTVModel`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 30000 });
          loadResults.ltv_models.push({ riskFactorId: body.riskFactorId, type: 'CollateralLTVModel', collateral_quantity: body.collateralQuantity, ltv_threshold: body.ltvThreshold, monitoring_points: body.monitoringEventTimes?.length || 0, status: 'loaded', server_response: typeof resp.data === 'string' ? resp.data.trim() : resp.data });
        } catch (err: any) { loadResults.ltv_models.push({ riskFactorId: body.riskFactorId, type: 'CollateralLTVModel', status: 'error', error: err.message }); }
      } else if (urlPath.includes('addScenario')) {
        try {
          const resp = await axios.post(`${riskUrl}/addScenario`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 30000 });
          loadResults.scenario = { scenarioID: body.scenarioID, risk_factors_count: body.riskFactorDescriptors?.length || 0, status: 'created', server_response: typeof resp.data === 'string' ? resp.data.trim() : resp.data };
        } catch (err: any) { loadResults.scenario = { scenarioID: body.scenarioID, status: 'error', error: err.message }; }
      } else if (urlPath.includes('scenarioSimulation') || urlPath.includes('rf2')) {
        try {
          const resp = await axios.post(`${simUrl}/rf2/scenarioSimulation`, body, { headers: { 'Content-Type': 'application/json' }, timeout: 60000 });
          const simResp = resp.data;
          const analysis: any = { total_events: 0, event_counts_by_type: {}, interventions: [], rate_summary: {}, loan_summary: {}, collateral_preserved: true };
          const contractResults: any[] = [];

          if (Array.isArray(simResp)) {
            for (const cr of simResp) {
              const events = cr.events || [];
              analysis.total_events += events.length;
              for (const e of events) analysis.event_counts_by_type[e.type] = (analysis.event_counts_by_type[e.type] || 0) + 1;
              const pps = events.filter((e: any) => e.type === 'PP');
              for (const pp of pps) analysis.interventions.push({ time: pp.time, payoff: pp.payoff, notional_after: pp.nominalValue, rate_at_time: pp.nominalRate });
              const rrs = events.filter((e: any) => e.type === 'RR');
              if (rrs.length > 0) {
                let mnR = Infinity, mxR = -Infinity, mnT = '', mxT = '';
                for (const rr of rrs) { if (rr.nominalRate < mnR) { mnR = rr.nominalRate; mnT = rr.time; } if (rr.nominalRate > mxR) { mxR = rr.nominalRate; mxT = rr.time; } }
                analysis.rate_summary = { initial: rrs[0].nominalRate, min: mnR, max: mxR, final: rrs[rrs.length - 1].nominalRate, min_time: mnT, max_time: mxT, total_resets: rrs.length };
              }
              const ied = events.find((e: any) => e.type === 'IED');
              const md = events.find((e: any) => e.type === 'MD');
              if (ied) {
                const ini = Math.abs(ied.nominalValue || ied.payoff || 0);
                const fin = md ? Math.abs(md.payoff || md.nominalValue || 0) : ini;
                const tp = pps.reduce((s: number, p: any) => s + Math.abs(p.payoff || 0), 0);
                analysis.loan_summary = { initial_notional: ini, final_notional: fin, total_prepaid: tp, total_deleveraged_pct: ini > 0 ? parseFloat(((tp / ini) * 100).toFixed(2)) : 0 };
              }
              contractResults.push({ contractId: cr.contractId || cr.contractID, status: cr.status, events_count: events.length, events });
            }
          }

          return res.json({
            source: 'live_actus_server', risk_server: riskUrl, simulation_server: simUrl,
            collection_file: `${category}/${filename}`, collection_name: collectionJson.info?.name || filename,
            simulation_metadata: { scenario_id: loadResults.scenario?.scenarioID || 'unknown', contracts_count: body.contracts?.length || 0, simulate_to: body.simulateTo, timestamp: new Date().toISOString() },
            market_risk_factors: loadResults, simulation_results: contractResults, analysis,
          });
        } catch (err: any) {
          return res.json({ source: 'live_actus_server', collection_file: `${category}/${filename}`, market_risk_factors: loadResults, simulation_error: err.message });
        }
      }
    }

    return res.json({ source: 'live_actus_server', collection_file: `${category}/${filename}`, market_risk_factors: loadResults, note: 'No scenarioSimulation step found' });
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

export default router;
