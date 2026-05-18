/**
 * Metric Calculation Utilities
 * Based on patterns from RiskLiquidityStableCoinOptimMerkleUtils.ts
 */

import type {
  ACTUSContract,
  ACTUSResponse,
  StableCoinRiskData,
  ReserveComponents,
  QualityMetrics,
  RiskMetrics
} from '../types/index.js';

/**
 * Process ACTUS response into StableCoin risk data structure
 */
export function processStableCoinData(
  actusResponse: ACTUSResponse,
  contracts: ACTUSContract[],
  backingRatioThreshold: number,
  liquidityRatioThreshold: number,
  concentrationLimit: number,
  qualityThreshold: number
): StableCoinRiskData {
  console.error('\n📊 Processing StableCoin data...');

  // If ACTUS returns 0 periods, default to 12 months
  let periodsCount = actusResponse.periodsCount;
  if (periodsCount === 0) {
    console.error('   \u26a0\ufe0f  ACTUS returned 0 periods, defaulting to 12 months');
    periodsCount = 12;
  }

  // Aggregate cash flows across all contracts.
  // inflow / outflow layout: inflow[period][contractIndex]
  // (outer = periods, inner = per-contract values within that period)
  // This matches the reference ACTUSOptimMerkleAPIResponse definition.
  const aggregatedInflows = new Array(periodsCount).fill(0);
  const aggregatedOutflows = new Array(periodsCount).fill(0);

  for (let period = 0; period < periodsCount; period++) {
    const periodInflows = actusResponse.inflow[period] || [];
    const periodOutflows = actusResponse.outflow[period] || [];
    aggregatedInflows[period] = periodInflows.reduce((sum: number, v: number) => sum + v, 0);
    aggregatedOutflows[period] = periodOutflows.reduce((sum: number, v: number) => sum + v, 0);
  }

  // Calculate total liabilities (outstanding tokens)
  const totalLiabilities = contracts
    .filter(c => c.contractRole === 'RPL')
    .reduce((sum, c) => sum + Math.abs(parseFloat(c.notionalPrincipal)), 0);

  console.error(`   Total Liabilities (Outstanding Tokens): ${totalLiabilities.toFixed(2)}`);

  const outstandingTokens = new Array(periodsCount).fill(totalLiabilities);
  const tokenValue = 1.0; // Assume $1 per token

  // Categorize reserves by type
  const reserveComponents = categorizeReserves(contracts, periodsCount);

  // Calculate quality metrics
  const qualityMetrics = calculateQualityMetrics(contracts);

  return {
    companyID: 'STABLECOIN_10001',
    companyName: 'StableCoin Reserve Assessment',
    cashInflow: aggregatedInflows,
    cashOutflow: aggregatedOutflows,
    periodsCount,
    reserveComponents,
    outstandingTokens,
    tokenValue,
    qualityMetrics,
    backingRatioThreshold,
    liquidityRatioThreshold,
    concentrationLimit,
    qualityThreshold
  };
}

/**
 * Categorize reserves into cash, treasury, corporate, and other
 * Based on contractID patterns from the portfolio
 */
function categorizeReserves(
  contracts: ACTUSContract[],
  periodsCount: number
): ReserveComponents {
  const cashReserves = new Array(periodsCount).fill(0);
  const treasuryReserves = new Array(periodsCount).fill(0);
  const corporateReserves = new Array(periodsCount).fill(0);
  const otherReserves = new Array(periodsCount).fill(0);
  const totalReserves = new Array(periodsCount).fill(0);

  // Process asset contracts (RPA role)
  contracts.forEach((contract) => {
    if (contract.contractRole !== 'RPA') return;

    const principal = Math.abs(parseFloat(contract.notionalPrincipal));
    const contractID = (contract.contractID || '').toLowerCase();

    // Categorize based on contractID patterns
    // cash01, cash02 -> Cash & Equivalents
    // treasury01 -> US Treasury Securities
    // corp01, corporate01 -> Corporate Bonds
    // everything else -> Other Assets
    for (let period = 0; period < periodsCount; period++) {
      if (contractID.includes('cash')) {
        cashReserves[period] += principal;
      } else if (contractID.includes('treasury') || contractID.includes('tbill')) {
        treasuryReserves[period] += principal;
      } else if (contractID.includes('corp') || contractID.includes('bond')) {
        corporateReserves[period] += principal;
      } else {
        otherReserves[period] += principal;
      }
      totalReserves[period] += principal;
    }
  });

  if (periodsCount > 0) {
    const total = totalReserves[0];
    const cashPct = total > 0 ? (cashReserves[0] / total * 100).toFixed(1) : '0.0';
    const treasuryPct = total > 0 ? (treasuryReserves[0] / total * 100).toFixed(1) : '0.0';
    const corpPct = total > 0 ? (corporateReserves[0] / total * 100).toFixed(1) : '0.0';
    const otherPct = total > 0 ? (otherReserves[0] / total * 100).toFixed(1) : '0.0';

    console.error(`   Cash & Equivalents: ${cashReserves[0].toFixed(0)} (${cashPct}%)`);
    console.error(`   US Treasury Securities: ${treasuryReserves[0].toFixed(0)} (${treasuryPct}%)`);
    console.error(`   Corporate Bonds: ${corporateReserves[0].toFixed(0)} (${corpPct}%)`);
    console.error(`   Other Assets: ${otherReserves[0].toFixed(0)} (${otherPct}%)`);
    console.error(`   Total Reserve Assets: ${total.toFixed(0)}`);
  } else {
    console.error(`   ⚠️  No periods returned from ACTUS - using static principal values`);
  }

  return {
    cashReserves,
    treasuryReserves,
    corporateReserves,
    otherReserves,
    totalReserves
  };
}

/**
 * Calculate quality metrics from contract attributes
 * Uses professional-grade quality scores based on asset categorization
 * Logic from RiskLiquidityStableCoinOptimMerkleUtils.ts
 */
function calculateQualityMetrics(contracts: ACTUSContract[]): QualityMetrics {
  const assetContracts = contracts.filter(c => c.contractRole === 'RPA');

  // Professional-grade quality metrics for institutional stablecoin reserves
  // [Cash, Treasury, Corporate, Other]
  const standardLiquidityScores = [100, 98, 75, 60];  // Cash, Treasury Bills, Corporate Bonds, Other
  const standardCreditRatings = [100, 100, 85, 70];   // Risk-free (Cash), Risk-free (UST), Investment Grade, Lower Grade
  const standardMaturityProfiles = [0, 60, 180, 365]; // Overnight, 60-day avg, 6-month avg, 1-year avg

  // Categorize contracts and calculate total amounts by category
  const categories = {
    cash: 0,
    treasury: 0,
    corporate: 0,
    other: 0
  };

  let totalAssets = 0;

  assetContracts.forEach(contract => {
    const principal = Math.abs(parseFloat(contract.notionalPrincipal));
    const contractID = (contract.contractID || '').toLowerCase();
    
    totalAssets += principal;

    // Categorize based on contractID patterns (same logic as categorizeReserves)
    if (contractID.includes('cash')) {
      categories.cash += principal;
    } else if (contractID.includes('treasury') || contractID.includes('tbill')) {
      categories.treasury += principal;
    } else if (contractID.includes('corp') || contractID.includes('bond')) {
      categories.corporate += principal;
    } else {
      categories.other += principal;
    }
  });

  // Calculate weighted asset quality score based on actual reserve composition
  const categoryAmounts = [categories.cash, categories.treasury, categories.corporate, categories.other];
  
  let weightedLiquidityScore = 0;
  let weightedCreditScore = 0;
  let weightedMaturityScore = 0;

  if (totalAssets > 0) {
    for (let i = 0; i < 4; i++) {
      const weight = categoryAmounts[i] / totalAssets;
      weightedLiquidityScore += standardLiquidityScores[i] * weight;
      weightedCreditScore += standardCreditRatings[i] * weight;
      weightedMaturityScore += standardMaturityProfiles[i] * weight;
    }
  }

  // Asset quality score is primarily based on liquidity and credit quality
  // For L1 HQLA assets (100% cash + treasury), this should approach 100
  const assetQualityScore = (weightedLiquidityScore * 0.6) + (weightedCreditScore * 0.4);

  return {
    liquidityScores: standardLiquidityScores,
    creditRatings: standardCreditRatings,
    maturityProfiles: standardMaturityProfiles,
    assetQualityScore: Math.round(assetQualityScore)
  };
}

/**
 * Calculate risk metrics from StableCoin data
 */
export function calculateRiskMetrics(data: StableCoinRiskData): RiskMetrics {
  console.error('\n📈 Calculating risk metrics...');

  const periodsCount = data.periodsCount;
  const backingRatios: number[] = [];
  const liquidityRatios: number[] = [];
  const concentrationRisks: number[] = [];
  const assetQualityScores: number[] = [];

  for (let period = 0; period < periodsCount; period++) {
    const totalReserves = data.reserveComponents.totalReserves[period];
    const outstandingTokens = data.outstandingTokens[period];
    const cashReserves = data.reserveComponents.cashReserves[period];
    const treasuryReserves = data.reserveComponents.treasuryReserves[period];

    // 1. Backing Ratio = (Total Reserves / Outstanding Tokens) * 100
    const backingRatio = outstandingTokens > 0 
      ? (totalReserves / outstandingTokens) * 100 
      : 0;
    backingRatios.push(backingRatio);

    // 2. Liquidity Ratio = (Highly Liquid Assets / Total Reserves) * 100
    // Per reference: calculateStableCoinRiskMetrics in RiskLiquidityStableCoinOptimMerkleUtils.ts
    //   "const liquidityRatio = totalReserves > 0 ? (liquidReserves / totalReserves) * 100 : 0"
    const highlyLiquidAssets = cashReserves + treasuryReserves;
    const liquidityRatio = totalReserves > 0
      ? (highlyLiquidAssets / totalReserves) * 100
      : 0;
    liquidityRatios.push(liquidityRatio);

    // 3. Concentration Risk = max percentage in any single category
    const cashPct = totalReserves > 0 ? (cashReserves / totalReserves) * 100 : 0;
    const treasuryPct = totalReserves > 0 ? (treasuryReserves / totalReserves) * 100 : 0;
    const corporatePct = totalReserves > 0 ? (data.reserveComponents.corporateReserves[period] / totalReserves) * 100 : 0;
    const otherPct = totalReserves > 0 ? (data.reserveComponents.otherReserves[period] / totalReserves) * 100 : 0;
    
    const concentrationRisk = Math.max(cashPct, treasuryPct, corporatePct, otherPct);
    concentrationRisks.push(concentrationRisk);

    // 4. Asset Quality Score (from quality metrics)
    assetQualityScores.push(data.qualityMetrics.assetQualityScore);
  }

  // Calculate aggregated metrics
  const averageBackingRatio = backingRatios.reduce((sum, v) => sum + v, 0) / periodsCount;
  const averageLiquidityRatio = liquidityRatios.reduce((sum, v) => sum + v, 0) / periodsCount;
  const maxConcentrationRisk = Math.max(...concentrationRisks);
  const averageAssetQuality = assetQualityScores.reduce((sum, v) => sum + v, 0) / periodsCount;

  // Check compliance
  const backingCompliant = backingRatios.every(r => r >= data.backingRatioThreshold);
  const liquidityCompliant = liquidityRatios.every(r => r >= data.liquidityRatioThreshold);
  const concentrationCompliant = concentrationRisks.every(r => r <= data.concentrationLimit);
  const qualityCompliant = averageAssetQuality >= data.qualityThreshold;
  const overallCompliant = backingCompliant && liquidityCompliant && concentrationCompliant && qualityCompliant;

  console.error(`   Average Backing Ratio: ${averageBackingRatio.toFixed(2)}%`);
  console.error(`   Average Liquidity Ratio: ${averageLiquidityRatio.toFixed(2)}%`);
  console.error(`   Max Concentration Risk: ${maxConcentrationRisk.toFixed(2)}%`);
  console.error(`   Asset Quality Score: ${averageAssetQuality.toFixed(2)}`);

  return {
    backingRatios,
    liquidityRatios,
    concentrationRisks,
    assetQualityScores,
    averageBackingRatio,
    averageLiquidityRatio,
    maxConcentrationRisk,
    averageAssetQuality,
    backingCompliant,
    liquidityCompliant,
    concentrationCompliant,
    qualityCompliant,
    overallCompliant
  };
}