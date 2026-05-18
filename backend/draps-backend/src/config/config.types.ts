/**
 * Configuration Type Definitions
 * Defines interfaces for the config-based simulation system
 */

export interface TimeSeriesData {
  time: string;
  value: number;
}

export interface JurisdictionParams {
  jurisdiction_code?: string;
  jurisdiction_name?: string;
  effective_date?: string;
  description?: string;
  backing_threshold: number;
  liquidity_threshold: number;
  wam_max_days: number;
  hqla_min_score: number;
  attestation_max_days: number;
  max_single_asset_share: number;
  hhi_warning_threshold: number;
  bank_stress_threshold: number;
  base_quality: number;
  quality_floor: number;
  sovereign_max_degradation: number;
}

export interface MarketScenarioData {
  scenario_name?: string;
  description?: string;
  scenario_date?: string;
  ISS_PEG_DEV_01?: TimeSeriesData[];
  ISS_PEG_RISK_01?: TimeSeriesData[];
  ISS_CURVE_01?: TimeSeriesData[];
  ISS_ORDERBOOK_01?: TimeSeriesData[];
  ISS_CEX_01?: TimeSeriesData[];
  ISS_SENT_01?: TimeSeriesData[];
  ISS_BANK_01?: TimeSeriesData[];
  ISS_SOV_01?: TimeSeriesData[];
  [key: string]: any;
}

export interface ComplianceScenarioData {
  scenario_name?: string;
  description?: string;
  ISS_BRISK_01?: TimeSeriesData[];
  ISS_LRISK_01?: TimeSeriesData[];
  ISS_QRISK_01?: TimeSeriesData[];
  ISS_CRISK_01?: TimeSeriesData[];
  ISS_CPRISK_01?: TimeSeriesData[];
  ISS_EWRISK_01?: TimeSeriesData[];
  [key: string]: any;
}

export interface IssuerConfig {
  config_metadata: {
    config_id: string;
    description?: string;
    version?: string;
    is_default?: boolean;
    collection_file: string;
  };
  
  jurisdiction: {
    source: 'inline' | 'file';
    file?: string;
    inline?: JurisdictionParams;
  };
  
  market_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: MarketScenarioData;
  };
  
  compliance_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: ComplianceScenarioData;
  };
  
  simulation_timeframe: {
    status_date?: string;
    start_date?: string;
    end_date?: string;
    duration_days?: number;
    frequency: 'daily' | 'weekly' | 'monthly';
  };
}

export interface HolderConfig {
  config_metadata: {
    config_id: string;
    description?: string;
    version?: string;
    is_default?: boolean;
    collection_file: string;
  };
  
  user_thresholds: {
    source: 'inline' | 'preset';
    preset?: string;
    inline?: {
      min_backing_ratio: number;
      max_wam_days: number;
      min_hqla_score: number;
      max_attestation_age_days: number;
      max_single_asset_concentration: number;
      max_peg_deviation: number;
      alert_on_bank_stress_above: number;
    };
  };
  
  simulation_timeframe: {
    status_date?: string;
    start_date?: string;
    end_date?: string;
    duration_days?: number;
    frequency: 'daily' | 'weekly' | 'monthly';
  };
}

export interface ResolvedConfig extends IssuerConfig {
  _resolved: true;
  jurisdiction_data: JurisdictionParams;
  market_scenario_data: MarketScenarioData;
  compliance_scenario_data: ComplianceScenarioData;
  generated: {
    monitoring_times: string[];
  };
}

export interface CollectionJSON {
  info: {
    name: string;
    description?: string;
    [key: string]: any;
  };
  variable?: Array<{
    key: string;
    value: string;
  }>;
  item: CollectionOperation[];
}

export interface CollectionOperation {
  name: string;
  request?: {
    method: string;
    url: any;
    header?: any[];
    body?: {
      mode: string;
      raw: string;
      [key: string]: any;
    };
  };
  item?: CollectionOperation[];
  event?: any[];
  [key: string]: any;
}

export interface MappingRules {
  [configPath: string]: string[];
}
