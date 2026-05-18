/**
 * DeFi Liquidation Simulation Routes
 * ====================================
 * Parallel to simulation.routes.ts (stablecoin) — completely new file,
 * zero edits to existing routes.
 *
 * Exposes:
 *   POST /api/defi-simulate          — run a DeFi liquidation simulation
 *   GET  /api/defi-profiles          — list all available borrower/protocol profiles
 *   GET  /api/defi-collections       — list available DeFi Postman collections
 */

import { Router } from 'express';
import type { Request, Response } from 'express';
import { loadDefiConfig, loadDefiCollection } from '../config/defi-config-loader.js';
import type { DefiBorrowerConfig, DefiProtocolConfig } from '../types/defi-config.types.js';
import { runStimulation, ENVIRONMENTS } from '../api/SimulationRunner.js';
import type { EnvironmentConfig } from '../api/SimulationRunner.js';

const router = Router();

// ─────────────────────────────────────────────────────────────────────────────
// POST /api/defi-simulate
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Run a DeFi liquidation simulation with config-based parameters.
 *
 * Request body:
 * {
 *   configData: DefiBorrowerConfig | DefiProtocolConfig,
 *   environment?: 'localhost' | 'aws',          // default: 'localhost'
 *   customUrls?: { riskServiceBase, actusServerBase }  // override environment
 * }
 *
 * Mirrors the POST /api/simulate endpoint in simulation.routes.ts exactly.
 */
router.post('/defi-simulate', async (req: Request, res: Response) => {
  try {
    const { configData, environment, customUrls } = req.body;

    if (!configData) {
      return res.status(400).json({
        success: false,
        error: 'Missing required field: configData',
      });
    }

    console.log('\n🔷 DeFi Liquidation Simulation Request');
    console.log('   Config ID  :', configData.config_metadata?.config_id);
    console.log('   Collection :', configData.config_metadata?.collection_file);

    // ── Step 1: Resolve environment ────────────────────────────────────────
    let envConfig: EnvironmentConfig;
    let envName: string;

    if (customUrls?.riskServiceBase && customUrls?.actusServerBase) {
      envConfig = {
        riskServiceBase: customUrls.riskServiceBase,
        actusServerBase: customUrls.actusServerBase,
      };
      envName = 'custom';
    } else {
      envName = environment || 'localhost';
      envConfig = ENVIRONMENTS[envName];
      if (!envConfig) {
        return res.status(400).json({
          success: false,
          error: `Unknown environment: "${envName}". Available: ${Object.keys(ENVIRONMENTS).join(', ')}`,
        });
      }
    }

    // ── Step 2: Load and resolve config ────────────────────────────────────
    const resolvedConfig = await loadDefiConfig(
      configData as DefiBorrowerConfig | DefiProtocolConfig
    );
    console.log('   ✅ Config resolved');
    console.log('   Protocol   :', resolvedConfig.protocol_data?.protocol_code ?? 'inline');
    console.log('   Monitoring times:', resolvedConfig.generated.monitoring_times.length);

    // ── Step 3: Load base Postman collection ───────────────────────────────
    const baseCollection = await loadDefiCollection(
      configData.config_metadata.collection_file
    );
    console.log('   ✅ Collection loaded:', baseCollection.info?.name);
    console.log('   Operations :', baseCollection.item?.length ?? 0);

    // ── Step 4: Run simulation via the shared SimulationRunner ────────────
    // SimulationRunner is unchanged — it auto-selects SIMPLE or SCRIPTED mode.
    console.log(`   🚀 Running ACTUS DeFi simulation (${envName})...`);
    const simulationResult = await runStimulation(baseCollection, envConfig, envName);

    if (!simulationResult.success) {
      return res.status(500).json({
        success: false,
        error: 'DeFi simulation failed',
        details: simulationResult,
      });
    }

    console.log('   ✅ Simulation complete');
    console.log('   Steps executed:', simulationResult.steps?.length ?? 0);
    console.log('   Simulation data:', simulationResult.simulation !== null ? 'present' : 'null');

    // ── Step 5: Determine entity type ─────────────────────────────────────
    const isBorrowerConfig = 'borrower_thresholds' in configData;
    const entityType = isBorrowerConfig ? 'borrower' : 'protocol';

    // ── Step 6: Return enriched result ────────────────────────────────────
    return res.json({
      ...simulationResult,
      configMetadata: {
        entity_type: entityType,
        protocol_code: resolvedConfig.protocol_data?.protocol_code ?? 'inline',
        monitoring_times_count: resolvedConfig.generated.monitoring_times.length,
        config_id: resolvedConfig.config_metadata.config_id,
        collection_file: resolvedConfig.config_metadata.collection_file,
        health_factor_trigger: resolvedConfig.protocol_data?.health_factor_trigger,
        healthy_health_factor: resolvedConfig.protocol_data?.healthy_health_factor,
        liquidation_threshold: resolvedConfig.protocol_data?.liquidation_threshold,
      },
      liquidationContext: {
        initial_health_factor: resolvedConfig.liquidation_scenario_data?.initial_health_factor,
        position_stress: resolvedConfig.liquidation_scenario_data?.position_stress,
        cascade_probability: resolvedConfig.liquidation_scenario_data?.liquidation_risk_metrics?.cascade_probability,
        time_to_liquidation_days: resolvedConfig.liquidation_scenario_data?.time_to_liquidation_days,
      },
    });

  } catch (error: any) {
    console.error('DeFi simulation error:', error);
    return res.status(500).json({
      success: false,
      error: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined,
    });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/defi-profiles
// ─────────────────────────────────────────────────────────────────────────────

/**
 * List all available DeFi borrower and protocol profiles.
 * Scans profiles/borrower and profiles/protocol directories.
 */
router.get('/defi-profiles', async (_req: Request, res: Response) => {
  try {
    const { promises: fs } = await import('fs');
    const path = await import('path');
    const { fileURLToPath } = await import('url');

    const __filename = fileURLToPath(import.meta.url);
    const __dirname  = path.dirname(__filename);
    const basePath   = path.join(
      __dirname, '..', '..', 'config', 'stimulation', 'defi-liquidation'
    );

    const profileDirs = [
      { type: 'borrower',  dir: path.join(basePath, 'profiles', 'borrower') },
      { type: 'protocol',  dir: path.join(basePath, 'profiles', 'protocol') },
      { type: 'default',   dir: path.join(basePath, 'defaults') },
    ];

    const results: any[] = [];

    for (const { type, dir } of profileDirs) {
      try {
        const files = (await fs.readdir(dir)).filter(f => f.endsWith('.json'));
        for (const filename of files) {
          try {
            const content = await fs.readFile(path.join(dir, filename), 'utf-8');
            const config  = JSON.parse(content);
            results.push({
              id:          `${type}/${filename.replace('.json', '')}`,
              type,
              filename,
              config_id:   config.config_metadata?.config_id ?? filename,
              description: config.config_metadata?.description ?? '',
              collection_file: config.config_metadata?.collection_file ?? '',
              protocol_source: config.protocol?.source ?? 'unknown',
            });
          } catch {
            /* skip malformed file */
          }
        }
      } catch {
        /* directory may not exist yet */
      }
    }

    return res.json(results);
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/defi-collections
// ─────────────────────────────────────────────────────────────────────────────

/**
 * List all available DeFi Postman collections.
 * Scans both defi-liquidation/defaults and the legacy defi-liquidity-collateral dirs.
 */
router.get('/defi-collections', async (_req: Request, res: Response) => {
  try {
    const { promises: fs } = await import('fs');
    const path = await import('path');
    const { fileURLToPath } = await import('url');

    const __filename = fileURLToPath(import.meta.url);
    const __dirname  = path.dirname(__filename);
    const stimPath   = path.join(__dirname, '..', '..', 'config', 'stimulation');

    const searchDirs = [
      path.join(stimPath, 'defi-liquidation', 'defaults'),
      path.join(stimPath, 'defi-liquidity-collateral', 'defi-liquidity-collateral-1'),
      path.join(stimPath, 'defi-liquidity-collateral', 'defi-liquidity-collateral-2'),
    ];

    const results: any[] = [];

    for (const dir of searchDirs) {
      try {
        const files = (await fs.readdir(dir))
          .filter(f => f.endsWith('.json') && !f.includes('postman_collection'));
        for (const filename of files) {
          try {
            const content    = await fs.readFile(path.join(dir, filename), 'utf-8');
            const collection = JSON.parse(content);
            if (!collection.info?.name) continue; // skip non-collection JSONs
            results.push({
              id:          filename.replace('.json', ''),
              filename,
              name:        collection.info.name,
              description: typeof collection.info.description === 'string'
                ? collection.info.description.slice(0, 200)
                : '',
              steps_count: collection.item?.length ?? 0,
              source_dir:  path.basename(path.dirname(dir)) + '/' + path.basename(dir),
            });
          } catch {
            /* skip */
          }
        }
      } catch {
        /* directory may not exist yet */
      }
    }

    return res.json(results);
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

export default router;
