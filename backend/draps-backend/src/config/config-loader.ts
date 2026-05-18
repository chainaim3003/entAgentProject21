/**
 * Config Loader
 * Loads config files and resolves file references
 */

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import type { IssuerConfig, HolderConfig, ResolvedConfig, JurisdictionParams, MarketScenarioData, ComplianceScenarioData } from './config.types.js';
import { generateMonitoringTimes } from './monitoring-time-generator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Load and resolve a config file
 */
export async function loadConfig(
  configData: IssuerConfig | HolderConfig
): Promise<ResolvedConfig> {
  const basePath = path.join(__dirname, '..', '..', 'config', 'stimulation', 'stablecoin');
  
  // Resolve jurisdiction
  let jurisdiction_data: JurisdictionParams;
  if ('jurisdiction' in configData) {
    if (configData.jurisdiction.source === 'file' && configData.jurisdiction.file) {
      const filePath = path.join(basePath, configData.jurisdiction.file);
      const content = await fs.readFile(filePath, 'utf-8');
      jurisdiction_data = JSON.parse(content);
    } else if (configData.jurisdiction.source === 'inline' && configData.jurisdiction.inline) {
      jurisdiction_data = configData.jurisdiction.inline;
    } else {
      throw new Error('Invalid jurisdiction configuration');
    }
  } else {
    // Holder config - use default US GENIUS
    const filePath = path.join(basePath, 'jurisdictions', 'us-genius.json');
    const content = await fs.readFile(filePath, 'utf-8');
    jurisdiction_data = JSON.parse(content);
  }
  
  // Resolve market scenario
  let market_scenario_data: MarketScenarioData = {};
  if ('market_scenario' in configData) {
    if (configData.market_scenario.source === 'file' && configData.market_scenario.file) {
      const filePath = path.join(basePath, configData.market_scenario.file);
      const content = await fs.readFile(filePath, 'utf-8');
      market_scenario_data = JSON.parse(content);
    } else if (configData.market_scenario.source === 'inline' && configData.market_scenario.inline) {
      market_scenario_data = configData.market_scenario.inline;
    }
  }
  
  // Resolve compliance scenario
  let compliance_scenario_data: ComplianceScenarioData = {};
  if ('compliance_scenario' in configData) {
    if (configData.compliance_scenario.source === 'file' && configData.compliance_scenario.file) {
      const filePath = path.join(basePath, configData.compliance_scenario.file);
      const content = await fs.readFile(filePath, 'utf-8');
      compliance_scenario_data = JSON.parse(content);
    } else if (configData.compliance_scenario.source === 'inline' && configData.compliance_scenario.inline) {
      compliance_scenario_data = configData.compliance_scenario.inline;
    }
  }
  
  // Generate monitoring times
  const { start_date, end_date, frequency } = configData.simulation_timeframe;
  let monitoring_times: string[] = [];
  
  if (start_date && end_date && frequency) {
    monitoring_times = generateMonitoringTimes(start_date, end_date, frequency);
  }
  
  // Build resolved config
  const resolved: ResolvedConfig = {
    ...(configData as IssuerConfig),
    _resolved: true,
    jurisdiction_data,
    market_scenario_data,
    compliance_scenario_data,
    generated: {
      monitoring_times
    }
  };
  
  return resolved;
}

/**
 * Load base collection file
 */
export async function loadCollection(collectionFile: string): Promise<any> {
  const basePath = path.join(__dirname, '..', '..', 'config', 'stimulation', 'stablecoin', 'defaults');
  const filePath = path.join(basePath, collectionFile);
  const content = await fs.readFile(filePath, 'utf-8');
  return JSON.parse(content);
}
