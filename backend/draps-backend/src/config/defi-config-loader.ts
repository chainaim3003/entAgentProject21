/**
 * DeFi Liquidation Config Loader
 * Parallel to config-loader.ts (stablecoin) — completely independent, no edits to existing file.
 *
 * Resolves file references in DefiBorrowerConfig / DefiProtocolConfig objects,
 * loads protocol params, market scenarios, liquidation scenarios, and generates
 * monitoring times — exactly the same pattern as the stablecoin loader.
 */

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import type {
  DefiBorrowerConfig,
  DefiProtocolConfig,
  DefiResolvedConfig,
  ProtocolParams,
  DefiMarketScenarioData,
  LiquidationScenarioData,
} from '../types/defi-config.types.js';
import { generateMonitoringTimes } from './monitoring-time-generator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

/** Base path for all defi-liquidation config files */
const DEFI_BASE = path.join(
  __dirname, '..', '..', 'config', 'stimulation', 'defi-liquidation'
);

// ─────────────────────────────────────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────────────────────────────────────

async function readJson<T>(filePath: string): Promise<T> {
  const content = await fs.readFile(filePath, 'utf-8');
  return JSON.parse(content) as T;
}

async function resolveProtocol(
  config: DefiBorrowerConfig | DefiProtocolConfig
): Promise<ProtocolParams> {
  const p = config.protocol;
  if (p.source === 'file' && p.file) {
    return readJson<ProtocolParams>(path.join(DEFI_BASE, p.file));
  }
  if (p.source === 'inline' && p.inline) {
    return p.inline;
  }
  throw new Error(
    `[defi-config-loader] Invalid protocol config in "${config.config_metadata.config_id}": ` +
    `source="${p.source}" but no file or inline data provided.`
  );
}

async function resolveMarketScenario(
  config: DefiBorrowerConfig | DefiProtocolConfig
): Promise<DefiMarketScenarioData> {
  const ms = config.market_scenario;
  if (ms.source === 'file' && ms.file) {
    return readJson<DefiMarketScenarioData>(path.join(DEFI_BASE, ms.file));
  }
  if (ms.source === 'inline' && ms.inline) {
    return ms.inline;
  }
  return {};
}

async function resolveLiquidationScenario(
  config: DefiBorrowerConfig | DefiProtocolConfig
): Promise<LiquidationScenarioData> {
  const ls = config.liquidation_scenario;
  if (ls.source === 'file' && ls.file) {
    return readJson<LiquidationScenarioData>(path.join(DEFI_BASE, ls.file));
  }
  if (ls.source === 'inline' && ls.inline) {
    return ls.inline;
  }
  return {};
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Load and fully resolve a DeFi borrower or protocol config.
 * Returns a DefiResolvedConfig with all file references expanded
 * and monitoring_times generated.
 */
export async function loadDefiConfig(
  configData: DefiBorrowerConfig | DefiProtocolConfig
): Promise<DefiResolvedConfig> {

  const [protocol_data, market_scenario_data, liquidation_scenario_data] =
    await Promise.all([
      resolveProtocol(configData),
      resolveMarketScenario(configData),
      resolveLiquidationScenario(configData),
    ]);

  // Generate monitoring times — reuses the existing stablecoin generator
  const { start_date, end_date, frequency } = configData.simulation_timeframe;
  let monitoring_times: string[] = [];
  if (start_date && end_date && frequency) {
    monitoring_times = generateMonitoringTimes(
      start_date,
      end_date,
      // generateMonitoringTimes only accepts daily/weekly/monthly;
      // hourly collections drive their own timestamps internally
      (frequency === 'hourly' ? 'daily' : frequency) as 'daily' | 'weekly' | 'monthly'
    );
  }

  const resolved: DefiResolvedConfig = {
    ...(configData as DefiBorrowerConfig),
    _resolved: true,
    protocol_data,
    market_scenario_data,
    liquidation_scenario_data,
    generated: { monitoring_times },
  };

  return resolved;
}

/**
 * Load a DeFi Postman collection file.
 * Searches: defi-liquidation/defaults, then all defi-liquidation-collateral subfolders.
 */
export async function loadDefiCollection(collectionFile: string): Promise<any> {
  const candidatePaths = [
    path.join(DEFI_BASE, 'defaults', collectionFile),
    path.join(
      __dirname, '..', '..', 'config', 'stimulation',
      'defi-liquidation-collateral', 'defi-liquidation-collateral-1', collectionFile
    ),
    path.join(
      __dirname, '..', '..', 'config', 'stimulation',
      'defi-liquidation-collateral', 'defi-liquidation-collateral-2', collectionFile
    ),
    path.join(
      __dirname, '..', '..', 'config', 'stimulation',
      'defi-liquidation-collateral', 'defi-liquidation-collateral-3', collectionFile
    ),
    path.join(
      __dirname, '..', '..', 'config', 'stimulation',
      'defi-liquidation-collateral', 'defi-liquidation-collateral-4', collectionFile
    ),
  ];

  for (const candidate of candidatePaths) {
    try {
      return await readJson<any>(candidate);
    } catch {
      // Not found at this path — try next
    }
  }

  throw new Error(
    `[defi-config-loader] Collection file not found: "${collectionFile}". ` +
    `Searched:\n  ${candidatePaths.join('\n  ')}`
  );
}
