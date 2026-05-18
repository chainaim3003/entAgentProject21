/**
 * DeFi Liquidation Configuration Type Definitions
 * Parallel to config.types.ts (stablecoin) — completely independent, no edits to existing types
 */

// ─────────────────────────────────────────────────────────────────────────────
// Shared primitives
// ─────────────────────────────────────────────────────────────────────────────

export interface TimeSeriesData {
  time: string;
  value: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Protocol parameters  (equivalent of JurisdictionParams)
// ─────────────────────────────────────────────────────────────────────────────

export interface ProtocolParams {
  protocol_code?: string;
  protocol_name?: string;
  version?: string;
  effective_date?: string;
  description?: string;

  // Core liquidation parameters
  liquidation_threshold: number;
  loan_to_value: number;
  liquidation_bonus: number;
  liquidation_close_factor: number;

  // Health factor thresholds
  health_factor_trigger: number;
  healthy_health_factor: number;
  target_health_factor_recovery: number;

  // Protocol economics
  reserve_factor: number;
  protocol_fee_bps: number;
  max_utilization_rate: number;
  stability_fee_annual?: number;

  // Collateral assets map (optional — may be in separate file)
  collateral_assets?: Record<string, CollateralAssetParams>;

  // Cascade / HHI risk
  cascade_risk?: {
    hhi_warning_threshold: number;
    max_single_collateral_share: number;
    correlation_penalty_threshold: number;
  };

  // Gas parameters
  gas_parameters?: {
    liquidation_gas_units: number;
    flash_loan_gas_units?: number;
    base_fee_gwei_reference: number;
    priority_fee_gwei: number;
  };

  [key: string]: any;
}

export interface CollateralAssetParams {
  liquidation_threshold: number;
  loan_to_value: number;
  liquidation_bonus: number;
  supply_cap_usd?: number;
  debt_ceiling_dai?: number;
  dust_minimum_dai?: number;
  stability_fee?: number;
  decimals: number;
  note?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Market scenario data  (equivalent of MarketScenarioData)
// ─────────────────────────────────────────────────────────────────────────────

export interface DefiMarketScenarioData {
  scenario_name?: string;
  description?: string;
  scenario_date?: string;
  collateral_stress?: 'none' | 'moderate' | 'severe';

  // Risk factor time-series (loaded from collection or inline)
  ETH_USD_01?: TimeSeriesData[];
  USDC_USD_01?: TimeSeriesData[];
  INV_PROB_01?: TimeSeriesData[];
  DEFI_RAT_HR_01?: TimeSeriesData[];
  GAS_PRICE_01?: TimeSeriesData[];
  CASCADE_PROB_01?: TimeSeriesData[];
  COLLAT_REBAL_01?: TimeSeriesData[];
  CORR_RISK_01?: TimeSeriesData[];

  [key: string]: any;
}

// ─────────────────────────────────────────────────────────────────────────────
// Liquidation scenario data  (equivalent of ComplianceScenarioData)
// ─────────────────────────────────────────────────────────────────────────────

export interface LiquidationScenarioData {
  scenario_name?: string;
  description?: string;
  position_stress?: 'none' | 'elevated' | 'critical';

  initial_health_factor?: number;
  collateral_basket?: {
    ETH_units?: number;
    ETH_price_usd?: number;
    USDC_amount?: number;
    invoice_amount?: number;
    [key: string]: any;
  };
  outstanding_loan_usdc?: number;
  ltv_current?: number;
  time_to_liquidation_days?: number;

  borrower_behavior?: {
    repay_trigger_health_factor: number;
    aggressive_repay_fraction: number;
    moderate_repay_fraction: number;
    safe_horizon_days: number;
    urgent_days: number;
  };

  liquidation_event?: {
    triggered: boolean;
    liquidation_type: string;
    close_factor: number;
    amount_to_liquidate_usd: number;
    liquidation_bonus_pct: number;
    liquidator_profit_usd: number;
    bad_debt_risk: boolean;
    gas_cost_gwei: number;
  };

  cascade_metrics?: {
    cascade_probability: number;
    cascade_depth_expected: number;
    correlated_positions_at_risk: number;
    estimated_cascade_volume_usd: number;
    protocol_insurance_fund_draw: boolean;
  };

  liquidation_risk_metrics?: {
    cascade_probability: number;
    collateral_velocity_alert: boolean;
    early_warning_active: boolean;
    velocity_implied_liquidation_days?: number;
    defensive_repay_usd?: number;
  };

  [key: string]: any;
}

// ─────────────────────────────────────────────────────────────────────────────
// Borrower thresholds  (equivalent of HolderConfig user_thresholds)
// ─────────────────────────────────────────────────────────────────────────────

export interface BorrowerThresholds {
  min_health_factor_comfort: number;
  repay_trigger_health_factor: number;
  aggressive_repay_fraction: number;
  moderate_repay_fraction: number;
  safe_horizon_days: number;
  urgent_days: number;
  max_ltv_target: number;
  gas_price_abort_gwei?: number;
  flash_loan_enabled?: boolean;
  flash_loan_max_usd?: number;
  hedge_delta_threshold?: number;
  rebalance_frequency_hours?: number;
  auto_top_up_collateral?: boolean;
  top_up_trigger_health_factor?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Protocol thresholds  (operator / risk manager view)
// ─────────────────────────────────────────────────────────────────────────────

export interface ProtocolThresholds {
  min_health_factor_trigger: number;
  healthy_health_factor: number;
  target_health_factor: number;
  max_liquidation_bonus: number;
  max_cascade_depth: number;
  min_collateral_ratio?: number;
  gas_price_gwei_limit?: number;
  max_slippage_tolerance?: number;
  liquidation_close_factor: number;
  protocol_fee_bps: number;
  stability_fee_annual?: number;
  auction_duration_hours?: number;
  circuit_breaker_active?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Config structures  (parallel to IssuerConfig / HolderConfig)
// ─────────────────────────────────────────────────────────────────────────────

/** Borrower config — mirrors IssuerConfig structure */
export interface DefiBorrowerConfig {
  config_metadata: {
    config_id: string;
    description?: string;
    version?: string;
    is_default?: boolean;
    collection_file: string;
  };

  protocol: {
    source: 'inline' | 'file';
    file?: string;
    inline?: ProtocolParams;
  };

  borrower_thresholds?: {
    source: 'inline' | 'preset';
    preset?: string;
    inline?: BorrowerThresholds;
  };

  market_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: DefiMarketScenarioData;
  };

  liquidation_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: LiquidationScenarioData;
  };

  simulation_timeframe: {
    status_date?: string;
    start_date?: string;
    end_date?: string;
    duration_days?: number;
    frequency: 'hourly' | 'daily' | 'weekly' | 'monthly';
  };
}

/** Protocol config — mirrors HolderConfig structure */
export interface DefiProtocolConfig {
  config_metadata: {
    config_id: string;
    description?: string;
    version?: string;
    is_default?: boolean;
    collection_file: string;
  };

  protocol: {
    source: 'inline' | 'file';
    file?: string;
    inline?: ProtocolParams;
  };

  protocol_thresholds: {
    source: 'inline' | 'preset';
    preset?: string;
    inline?: ProtocolThresholds;
  };

  market_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: DefiMarketScenarioData;
  };

  liquidation_scenario: {
    source: 'inline' | 'file';
    file?: string;
    inline?: LiquidationScenarioData;
  };

  simulation_timeframe: {
    status_date?: string;
    start_date?: string;
    end_date?: string;
    duration_days?: number;
    frequency: 'hourly' | 'daily' | 'weekly' | 'monthly';
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Resolved config  (parallel to ResolvedConfig for stablecoin)
// ─────────────────────────────────────────────────────────────────────────────

export interface DefiResolvedConfig extends DefiBorrowerConfig {
  _resolved: true;
  protocol_data: ProtocolParams;
  market_scenario_data: DefiMarketScenarioData;
  liquidation_scenario_data: LiquidationScenarioData;
  generated: {
    monitoring_times: string[];
  };
}
