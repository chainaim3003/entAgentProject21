/**
 * Data Validation Utilities
 */

import type { StableCoinRiskData, RiskMetrics, VerificationSummary } from '../types/index.js';

/**
 * Validate StableCoin risk data integrity
 */
export function validateStableCoinData(data: StableCoinRiskData): void {
  console.error('\n🔍 Validating data integrity...');

  // Validate periodsCount
  if (data.periodsCount <= 0) {
    throw new Error('Periods count must be positive');
  }

  // Validate array lengths
  if (data.cashInflow.length !== data.periodsCount) {
    throw new Error(`Cash inflow length (${data.cashInflow.length}) does not match periods count (${data.periodsCount})`);
  }

  if (data.cashOutflow.length !== data.periodsCount) {
    throw new Error(`Cash outflow length (${data.cashOutflow.length}) does not match periods count (${data.periodsCount})`);
  }

  // Validate thresholds
  if (data.backingRatioThreshold <= 0) {
    throw new Error('Backing ratio threshold must be positive');
  }

  if (data.liquidityRatioThreshold < 0) {
    throw new Error('Liquidity ratio threshold cannot be negative');
  }

  if (data.concentrationLimit <= 0 || data.concentrationLimit > 100) {
    throw new Error('Concentration limit must be between 0 and 100');
  }

  if (data.qualityThreshold < 0 || data.qualityThreshold > 100) {
    throw new Error('Quality threshold must be between 0 and 100');
  }

  // Validate quality metrics arrays
  if (data.qualityMetrics.liquidityScores.length !== 4) {
    throw new Error('Liquidity scores must have exactly 4 elements (cash, treasury, corporate, other)');
  }

  if (data.qualityMetrics.creditRatings.length !== 4) {
    throw new Error('Credit ratings must have exactly 4 elements (cash, treasury, corporate, other)');
  }

  if (data.qualityMetrics.maturityProfiles.length !== 4) {
    throw new Error('Maturity profiles must have exactly 4 elements (cash, treasury, corporate, other)');
  }

  console.error('✅ Data validation passed');
}

/**
 * Generate verification summary from risk metrics
 */
export function generateSummary(
  portfolioId: string,
  riskMetrics: RiskMetrics,
  data: StableCoinRiskData
): VerificationSummary {
  const failureReasons: string[] = [];

  // Check backing ratio
  const backingStatus: 'PASS' | 'FAIL' = riskMetrics.backingCompliant ? 'PASS' : 'FAIL';
  if (!riskMetrics.backingCompliant) {
    failureReasons.push(
      `Backing ratio (${riskMetrics.averageBackingRatio.toFixed(2)}%) below threshold (${data.backingRatioThreshold}%)`
    );
  }

  // Check liquidity ratio
  const liquidityStatus: 'PASS' | 'FAIL' = riskMetrics.liquidityCompliant ? 'PASS' : 'FAIL';
  if (!riskMetrics.liquidityCompliant) {
    failureReasons.push(
      `Liquidity ratio (${riskMetrics.averageLiquidityRatio.toFixed(2)}%) below threshold (${data.liquidityRatioThreshold}%)`
    );
  }

  // Check concentration risk
  const concentrationStatus: 'PASS' | 'FAIL' = riskMetrics.concentrationCompliant ? 'PASS' : 'FAIL';
  if (!riskMetrics.concentrationCompliant) {
    failureReasons.push(
      `Concentration risk (${riskMetrics.maxConcentrationRisk.toFixed(2)}%) exceeds limit (${data.concentrationLimit}%)`
    );
  }

  // Check quality score
  const qualityStatus: 'PASS' | 'FAIL' = riskMetrics.qualityCompliant ? 'PASS' : 'FAIL';
  if (!riskMetrics.qualityCompliant) {
    failureReasons.push(
      `Asset quality score (${riskMetrics.averageAssetQuality.toFixed(2)}) below threshold (${data.qualityThreshold})`
    );
  }

  // Overall status
  const overallStatus: 'COMPLIANT' | 'NON-COMPLIANT' = riskMetrics.overallCompliant 
    ? 'COMPLIANT' 
    : 'NON-COMPLIANT';

  return {
    portfolioId,
    periodsAnalyzed: data.periodsCount,
    backing: {
      average: riskMetrics.averageBackingRatio,
      threshold: data.backingRatioThreshold,
      status: backingStatus
    },
    liquidity: {
      average: riskMetrics.averageLiquidityRatio,
      threshold: data.liquidityRatioThreshold,
      status: liquidityStatus
    },
    concentration: {
      maximum: riskMetrics.maxConcentrationRisk,
      limit: data.concentrationLimit,
      status: concentrationStatus
    },
    quality: {
      score: riskMetrics.averageAssetQuality,
      threshold: data.qualityThreshold,
      status: qualityStatus
    },
    overallStatus,
    failureReasons
  };
}

/**
 * Display verification summary in formatted output
 */
export function displaySummary(summary: VerificationSummary): void {
  console.error('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.error('📊 VERIFICATION SUMMARY');
  console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  console.error(`Portfolio ID: ${summary.portfolioId}`);
  console.error(`Periods Analyzed: ${summary.periodsAnalyzed}\n`);

  // Backing Ratio
  const backingIcon = summary.backing.status === 'PASS' ? '✅' : '❌';
  console.error(`${backingIcon} Backing Ratio:`);
  console.error(`   Average: ${summary.backing.average.toFixed(2)}%`);
  console.error(`   Threshold: ${summary.backing.threshold}%`);
  console.error(`   Status: ${summary.backing.status}\n`);

  // Liquidity Ratio
  const liquidityIcon = summary.liquidity.status === 'PASS' ? '✅' : '❌';
  console.error(`${liquidityIcon} Liquidity Ratio:`);
  console.error(`   Average: ${summary.liquidity.average.toFixed(2)}%`);
  console.error(`   Threshold: ${summary.liquidity.threshold}%`);
  console.error(`   Status: ${summary.liquidity.status}\n`);

  // Concentration Risk
  const concentrationIcon = summary.concentration.status === 'PASS' ? '✅' : '❌';
  console.error(`${concentrationIcon} Concentration Risk:`);
  console.error(`   Maximum: ${summary.concentration.maximum.toFixed(2)}%`);
  console.error(`   Limit: ${summary.concentration.limit}%`);
  console.error(`   Status: ${summary.concentration.status}\n`);

  // Asset Quality
  const qualityIcon = summary.quality.status === 'PASS' ? '✅' : '❌';
  console.error(`${qualityIcon} Asset Quality:`);
  console.error(`   Score: ${summary.quality.score.toFixed(2)}`);
  console.error(`   Threshold: ${summary.quality.threshold}`);
  console.error(`   Status: ${summary.quality.status}\n`);

  // Overall Status
  console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  const overallIcon = summary.overallStatus === 'COMPLIANT' ? '🎉' : '⚠️';
  console.error(`${overallIcon} OVERALL STATUS: ${summary.overallStatus}`);
  console.error('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  // Failure Reasons
  if (summary.failureReasons.length > 0) {
    console.error('❌ Failure Reasons:');
    summary.failureReasons.forEach(reason => {
      console.error(`   • ${reason}`);
    });
    console.error('');
  }
}