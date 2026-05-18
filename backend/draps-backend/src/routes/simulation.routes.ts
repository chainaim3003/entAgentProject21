/**
 * Simulation Routes
 * Config-based simulation endpoint that runs full ACTUS simulation
 */

import { Router } from 'express';
import type { Request, Response } from 'express';
import { loadConfig, loadCollection } from '../config/config-loader.js';
import type { IssuerConfig, HolderConfig } from '../config/config.types.js';
import { runStimulation, ENVIRONMENTS } from '../api/SimulationRunner.js';
import type { EnvironmentConfig } from '../api/SimulationRunner.js';
import { promises as fsPromises } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = Router();

// ═══════════════════════════════════════════════════════════════════
// Existing route — untouched
// ═══════════════════════════════════════════════════════════════════

/**
 * POST /api/simulate
 * Run simulation with config-based parameters
 */
router.post('/simulate', async (req: Request, res: Response) => {
  try {
    const { configData } = req.body;
    
    if (!configData) {
      return res.status(400).json({
        success: false,
        error: 'Missing required field: configData'
      });
    }
    
    console.log('\n🎯 Config-Based Simulation Request');
    console.log('   Config ID:', configData.config_metadata?.config_id);
    console.log('   Collection:', configData.config_metadata?.collection_file);
    console.log('   Inline mode:', !!configData.config_metadata?.collection_inline);
    
    const resolvedConfig = await loadConfig(configData as IssuerConfig | HolderConfig);
    console.log('   ✅ Config resolved');
    console.log('   Jurisdiction:', resolvedConfig.jurisdiction_data.jurisdiction_code);
    console.log('   Monitoring times generated:', resolvedConfig.generated.monitoring_times.length);
    
    // OPTION 2: if caller shipped collection_inline, use that and skip disk load.
    // Otherwise fall back to loadCollection() so legacy callers keep working.
    const baseCollection = configData.config_metadata.collection_inline
      ?? await loadCollection(configData.config_metadata.collection_file);
    console.log('   ✅ Base collection loaded');
    console.log('   Collection name:', baseCollection.info?.name);
    console.log('   Operations:', baseCollection.item?.length || 0);
    
    console.log('   🚀 Running ACTUS simulation...');
    const envConfig = ENVIRONMENTS.localhost;
    const simulationResult = await runStimulation(baseCollection, envConfig, 'localhost');
    
    if (!simulationResult.success) {
      return res.status(500).json({
        success: false,
        error: 'Simulation failed',
        details: simulationResult
      });
    }
    
    console.log('   ✅ Simulation complete');
    console.log('   Steps executed:', simulationResult.steps?.length || 0);
    console.log('   Contracts:', simulationResult.simulation?.length || 0);
    
    return res.json({
      ...simulationResult,
      configMetadata: {
        entity_type: configData.config_metadata.collection_file.includes('ISS') ? 'issuer' : 'holder',
        jurisdiction: resolvedConfig.jurisdiction_data.jurisdiction_code,
        monitoring_times_count: resolvedConfig.generated.monitoring_times.length,
        config_id: resolvedConfig.config_metadata.config_id,
        collection_file: resolvedConfig.config_metadata.collection_file
      }
    });
    
  } catch (error: any) {
    console.error('Simulation error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
});

// ═══════════════════════════════════════════════════════════════════
// NEW: Stablecoin simulation with inline threshold overrides
// ═══════════════════════════════════════════════════════════════════

/**
 * Load a stablecoin base collection from disk.
 */
async function loadStablecoinCollection(entityType: 'issuer' | 'holder'): Promise<any> {
  const filename = entityType === 'issuer'
    ? 'Stables-HT-ISS-time-daily-5.json'
    : 'Stables-HT-HOL-ONLY-3RD-SOURCE-time-daily-5.json';
  const filePath = path.join(
    __dirname, '..', '..', 'config', 'stimulation', 'stablecoin', 'defaults', filename,
  );
  const content = await fsPromises.readFile(filePath, 'utf-8');
  return JSON.parse(content);
}

/**
 * Recursively find a Postman item by name substring.
 */
function findItemByName(items: any[], nameSubstring: string): any | null {
  for (const item of items) {
    if (item.name && String(item.name).includes(nameSubstring)) return item;
    if (item.item && Array.isArray(item.item)) {
      const found = findItemByName(item.item, nameSubstring);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Parse a Postman item's body.raw as JSON, apply field overrides, stringify back.
 * Only modifies fields that exist in `overrides`. Safe no-op if item/body missing.
 */
function patchItemBody(item: any, overrides: Record<string, unknown>): void {
  if (!item?.request?.body?.raw) return;
  try {
    const body = JSON.parse(item.request.body.raw);
    let changed = false;
    for (const [key, value] of Object.entries(overrides)) {
      if (value !== undefined && value !== null) {
        body[key] = value;
        changed = true;
      }
    }
    if (changed) {
      item.request.body.raw = JSON.stringify(body, null, 2);
    }
  } catch {
    // Body not valid JSON — skip
  }
}

/**
 * Apply issuer threshold overrides to the ISS collection.
 *
 * Modifies the behavioral model registration bodies (Phase 2 steps)
 * which are POSTed to the ACTUS risk service (8082).
 * The ACTUS Java server uses these thresholds during the simulation.
 */
function applyIssuerOverrides(collection: any, thresholds: Record<string, number>): void {
  const items = collection.item || [];

  // BackingRatioModel — controls backing ratio compliance check
  const brItem = findItemByName(items, 'BackingRatioModel');
  if (brItem) {
    patchItemBody(brItem, {
      backingThreshold: thresholds.backingThreshold,
    });
  }

  // ComplianceDriftModel — controls liquidity and WAM compliance
  const cpItem = findItemByName(items, 'ComplianceDriftModel');
  if (cpItem) {
    patchItemBody(cpItem, {
      liquidityThreshold: thresholds.liquidityThreshold,
      wamMaxDays: thresholds.wamMaxDays,
    });
  }

  // AssetQualityModel — controls quality degradation rules
  const aqItem = findItemByName(items, 'AssetQualityModel');
  if (aqItem) {
    patchItemBody(aqItem, {
      bankStressThreshold: thresholds.bankStressThreshold,
      baseQuality: thresholds.baseQuality,
      qualityFloor: thresholds.qualityFloor,
      sovereignMaxDegradation: thresholds.sovereignMaxDegradation,
    });
  }

  // ConcentrationDriftModel — controls concentration risk limits
  const cdItem = findItemByName(items, 'ConcentrationDriftModel');
  if (cdItem) {
    patchItemBody(cdItem, {
      maxSingleAssetShare: thresholds.maxSingleAssetShare,
      hhiWarningThreshold: thresholds.hhiWarningThreshold,
    });
  }

  console.log('   ✅ Issuer thresholds injected into collection');
}

/**
 * Apply holder threshold overrides to the HOL collection.
 *
 * Modifies:
 *   1. Collection variables (cfg_initial_usd, cfg_target_usdc, cfg_deploy_pct)
 *   2. The prerequest script's isGood/isBad threshold lines
 */
function applyHolderOverrides(
  collection: any,
  portfolio: { initialUsd: number; targetUsdc: number; deployPct: number },
  good: { br: number; lq: number; peg: number; mr: number; hqla: number; cc: number },
  bad: { br: number; lq: number; peg: number; mr: number; hqla: number; cc: number },
): void {
  // 1. Override collection variables
  const vars: any[] = collection.variable || [];
  for (const v of vars) {
    if (v.key === 'cfg_initial_usd') v.value = String(portfolio.initialUsd);
    if (v.key === 'cfg_target_usdc') v.value = String(portfolio.targetUsdc);
    if (v.key === 'cfg_deploy_pct') v.value = String(portfolio.deployPct);
    // Reset runtime state for clean run
    if (v.key === 'rt_epoch') v.value = '0';
    if (v.key === 'rt_usd') v.value = String(portfolio.initialUsd);
    if (v.key === 'rt_usdc') v.value = '0';
    if (v.key === 'rt_history') v.value = '[]';
  }

  // 2. Find the "2.1 Daily Portfolio Manager" prerequest script and replace threshold lines
  const managerItem = findItemByName(collection.item || [], 'Daily Portfolio Manager');
  if (!managerItem) {
    console.warn('   ⚠️  Could not find Daily Portfolio Manager item');
    return;
  }

  const prereqEvent = (managerItem.event || []).find((e: any) => e.listen === 'prerequest');
  if (!prereqEvent?.script?.exec || !Array.isArray(prereqEvent.script.exec)) {
    console.warn('   ⚠️  Could not find prerequest script in Daily Portfolio Manager');
    return;
  }

  const exec: string[] = prereqEvent.script.exec;

  // Replace the isGood line
  const goodLine = `var isGood = (br < ${good.br} && lq < ${good.lq} && peg < ${good.peg} && mr < ${good.mr} && hqla >= ${good.hqla} && cc < ${good.cc});`;
  for (let i = 0; i < exec.length; i++) {
    if (exec[i].includes('var isGood')) {
      exec[i] = goodLine;
      break;
    }
  }

  // Replace the isBad line
  const badLine = `var isBad = (br > ${bad.br} || lq > ${bad.lq} || peg > ${bad.peg} || mr > ${bad.mr} || hqla < ${bad.hqla} || cc > ${bad.cc});`;
  for (let i = 0; i < exec.length; i++) {
    if (exec[i].includes('var isBad')) {
      exec[i] = badLine;
      break;
    }
  }

  console.log('   ✅ Holder thresholds + portfolio config injected');
}

/**
 * POST /api/stablecoin-simulate
 *
 * Runs the ISS or HOL stablecoin collection with user-provided threshold overrides.
 * The base collection is loaded from disk, thresholds are injected, then executed.
 */
router.post('/stablecoin-simulate', async (req: Request, res: Response) => {
  try {
    const {
      entityType,
      environment,
      issuerThresholds,
      holderPortfolio,
      holderGood,
      holderBad,
    } = req.body;

    if (!entityType || (entityType !== 'issuer' && entityType !== 'holder')) {
      return res.status(400).json({
        success: false,
        error: 'Missing or invalid entityType. Must be "issuer" or "holder".',
      });
    }

    console.log(`\n🔷 Stablecoin Simulation [${entityType.toUpperCase()}]`);

    // 1. Resolve environment
    const envName = environment || 'localhost';
    const envConfig: EnvironmentConfig = ENVIRONMENTS[envName];
    if (!envConfig) {
      return res.status(400).json({
        success: false,
        error: `Unknown environment: "${envName}". Available: ${Object.keys(ENVIRONMENTS).join(', ')}`,
      });
    }

    // 2. Load base collection (deep clone via parse/stringify)
    const baseCollection = await loadStablecoinCollection(entityType);
    const collection = JSON.parse(JSON.stringify(baseCollection));
    console.log('   ✅ Base collection loaded:', collection.info?.name);

    // 3. Apply threshold overrides
    if (entityType === 'issuer' && issuerThresholds) {
      applyIssuerOverrides(collection, issuerThresholds);
      console.log('   Thresholds:', JSON.stringify(issuerThresholds));
    } else if (entityType === 'holder') {
      const portfolio = holderPortfolio || { initialUsd: 150000, targetUsdc: 75000, deployPct: 30 };
      const good = holderGood || { br: 0.05, lq: 0.10, peg: 0.01, mr: 0.10, hqla: 95, cc: 0.15 };
      const bad = holderBad || { br: 0.10, lq: 0.30, peg: 0.02, mr: 0.20, hqla: 90, cc: 0.40 };
      applyHolderOverrides(collection, portfolio, good, bad);
      console.log('   Portfolio:', JSON.stringify(portfolio));
      console.log('   Good thresholds:', JSON.stringify(good));
      console.log('   Bad thresholds:', JSON.stringify(bad));
    }

    // 4. Run via SimulationRunner
    console.log(`   🚀 Running ACTUS simulation (${envName})...`);
    const result = await runStimulation(collection, envConfig, envName);

    console.log('   ✅ Simulation complete');
    console.log('   Steps:', result.steps?.length || 0);
    console.log('   Success:', result.success);

    // 5. Return result
    return res.json({
      ...result,
      entityType,
      appliedThresholds: entityType === 'issuer' ? issuerThresholds : {
        portfolio: holderPortfolio,
        good: holderGood,
        bad: holderBad,
      },
    });

  } catch (error: any) {
    console.error('Stablecoin simulation error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

export default router;
