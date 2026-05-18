/**
 * Type definitions for RiskStableCoin Verifier
 * Simplified types without ZK or Network components
 */

// ============================================
// ACTUS Contract Types
// ============================================

export interface ACTUSContract {
  contractType: string;
  contractID: string;
  contractRole: string; // 'RPA' for assets, 'RPL' for liabilities
  contractDealDate?: string;
  initialExchangeDate?: string;
  statusDate: string;
  notionalPrincipal: string;
  currency: string;
  
  // StableCoin-specific attributes
  reserveType?: 'cash' | 'treasury' | 'corporate' | 'other';
  liquidityScore?: number; // 0-100
  creditRating?: number; // 0-100
  maturityDays?: number;
  
  [key: string]: any; // Additional contract-specific fields
}

export interface ACTUSRequestData {
  contracts: ACTUSContract[];
  riskFactors: any[];
}

export interface ACTUSResponse {
  inflow: number[][];
  outflow: number[][];
  periodsCount: number;
  contractDetails: any[];
  riskMetrics?: any;
  metadata?: {
    timeHorizon?: string;
    currency?: string;
    processingDate?: string;
  };
}

// ============================================
// Portfolio Configuration Types
// ============================================

export interface PortfolioMetadata {
  portfolioId: string;
  totalNotional: number;
  currency: string;
  description?: string;
}

export interface PortfolioConfig {
  portfolioMetadata: PortfolioMetadata;
  contracts: ACTUSContract[];
}

// ============================================
// Verification Parameters
// ============================================

export interface VerificationParams {
  backingRatioThreshold: number; // e.g., 100 for 100%
  liquidityRatioThreshold: number; // e.g., 20 for 20%
  concentrationLimit: number; // e.g., 25 for 25%
  qualityThreshold: number; // e.g., 80 for score of 80
  actusUrl: string;
  portfolioPath: string;
}

// ============================================
// Reserve Components
// ============================================

export interface ReserveComponents {
  cashReserves: number[];
  treasuryReserves: number[];
  corporateReserves: number[];
  otherReserves: number[];
  totalReserves: number[];
}

// ============================================
// Quality Metrics
// ============================================

export interface QualityMetrics {
  liquidityScores: number[]; // [cash, treasury, corporate, other]
  creditRatings: number[];
  maturityProfiles: number[];
  assetQualityScore: number;
}

// ============================================
// Risk Metrics
// ============================================

export interface RiskMetrics {
  // Per-period arrays
  backingRatios: number[];
  liquidityRatios: number[];
  concentrationRisks: number[];
  assetQualityScores: number[];
  
  // Aggregated metrics
  averageBackingRatio: number;
  averageLiquidityRatio: number;
  maxConcentrationRisk: number;
  averageAssetQuality: number;
  
  // Compliance flags
  backingCompliant: boolean;
  liquidityCompliant: boolean;
  concentrationCompliant: boolean;
  qualityCompliant: boolean;
  overallCompliant: boolean;
}

// ============================================
// StableCoin Risk Data
// ============================================

export interface StableCoinRiskData {
  // Identifiers
  companyID: string;
  companyName: string;
  
  // Cash flow data
  cashInflow: number[];
  cashOutflow: number[];
  periodsCount: number;
  
  // Reserve components
  reserveComponents: ReserveComponents;
  outstandingTokens: number[];
  tokenValue: number;
  
  // Quality metrics
  qualityMetrics: QualityMetrics;
  
  // Thresholds
  backingRatioThreshold: number;
  liquidityRatioThreshold: number;
  concentrationLimit: number;
  qualityThreshold: number;
}

// ============================================
// Verification Result
// ============================================

export interface VerificationResult {
  success: boolean;
  compliant: boolean;
  riskMetrics: RiskMetrics;
  summary: VerificationSummary;
  timestamp: string;
}

export interface VerificationSummary {
  portfolioId: string;
  periodsAnalyzed: number;
  
  backing: {
    average: number;
    threshold: number;
    status: 'PASS' | 'FAIL';
  };
  
  liquidity: {
    average: number;
    threshold: number;
    status: 'PASS' | 'FAIL';
  };
  
  concentration: {
    maximum: number;
    limit: number;
    status: 'PASS' | 'FAIL';
  };
  
  quality: {
    score: number;
    threshold: number;
    status: 'PASS' | 'FAIL';
  };
  
  overallStatus: 'COMPLIANT' | 'NON-COMPLIANT';
  failureReasons: string[];
}
