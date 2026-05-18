/**
 * ACTUS Server Client
 * Handles communication with ACTUS server for cash flow data
 *
 * Uses standardized post-processing logic from ACTUSDataProcessor.ts
 * This ensures consistency across all ACTUS integrations
 */

import axios from 'axios';
import type { ACTUSContract, ACTUSRequestData, ACTUSResponse } from '../types/index.js';
import { processRawACTUSData, printCoreACTUSResponse } from '../utils/ACTUSDataProcessor.js';

export class ACTUSClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  // =================================== Main Entry Point ===================================

  /**
   * Call ACTUS API with contract portfolio and post-processing.
   *
   * Handles two response formats returned by ACTUS /eventsBatch:
   *   1. Structured format  – { inflow, outflow, monthsCount, ... }
   *   2. Raw events format  – [ { contractId, events:[{time, payoff}] } ]
   *
   * Post-processing mirrors EXACTLY:
   *   ACTUSDataProcessor.callACTUSAPIWithPostProcessing()
   */
  async fetchCashFlowData(contracts: ACTUSContract[]): Promise<ACTUSResponse> {
    // Clean contracts before sending (remove non-ACTUS fields)
    const cleanedContracts = contracts.map(contract => {
      const { reserveType, liquidityScore, creditRating, maturityDays, ...cleanContract } = contract;
      return cleanContract;
    });

    const requestData: ACTUSRequestData = {
      contracts: cleanedContracts,
      riskFactors: []
    };

    console.error('\n=== CALLING ACTUS API WITH POST-PROCESSING ===');
    console.error(`URL: ${this.baseUrl}`);
    console.error(`Sending ${cleanedContracts.length} contracts`);
    console.error('Contract IDs:', cleanedContracts.map(c => c.contractID));

    try {
      const response = await axios.post(this.baseUrl, requestData, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000
      });

      // Print core ACTUS response for debugging (using standardized function)
      printCoreACTUSResponse(response, this.baseUrl);

      const rawData = response.data;

      // ----------------------------------------------------------------
      // Path 1: Response already has structured inflow/outflow/monthsCount
      // (EXACT check from ACTUSDataProcessor.ts line 283)
      // ----------------------------------------------------------------
      if (rawData && Array.isArray(rawData.inflow) && rawData.monthsCount > 0) {
        console.error('✅ Response already in expected format with proper periods');
        return {
          inflow: rawData.inflow,
          outflow: rawData.outflow,
          periodsCount: rawData.monthsCount,
          contractDetails: rawData.contractDetails || [],
          riskMetrics: rawData.riskMetrics || {},
          metadata: {
            timeHorizon: 'monthly',
            currency: 'USD',
            processingDate: new Date().toISOString()
          }
        };
      }

      // ----------------------------------------------------------------
      // Path 2: Raw events array from /eventsBatch
      // Transform and apply post-processing
      // (Uses standardized ACTUSDataProcessor logic)
      // ----------------------------------------------------------------
      console.error('⚠️ Response is raw contract events - applying post-processing...');

      // Transform the API response to match the format expected by processRawACTUSData
      const transformedData = rawData.map((contractResponse: any) => ({
        id: contractResponse.contractId || contractResponse.contractID,
        contractId: contractResponse.contractId || contractResponse.contractID,
        type: 'unknown',
        events: contractResponse.events || []
      }));

      // Apply standardized post-processing logic from ACTUSDataProcessor
      const processedData = processRawACTUSData(transformedData);
      const actusResponse = this.convertToACTUSResponse(processedData);

      console.error(`✅ Post-processing complete: ${actusResponse.periodsCount} periods generated`);
      console.error('=== END ACTUS API CALL WITH POST-PROCESSING ===\n');

      return actusResponse;

    } catch (error: any) {
      console.error('❌ ACTUS API call failed:', error.message);

      if (error.response) {
        console.error(`   Status: ${error.response.status}`);
        console.error(`   Data:`, error.response.data);
      } else if (error.request) {
        console.error('   No response received from server');
        console.error('   Please ensure ACTUS server is running');
      }

      throw new Error(`ACTUS API call failed: ${error.message}`);
    }
  }

  // =================================== Format Conversion ===================================

  /**
   * Convert processed ACTUS data to ACTUSResponse format
   * (Uses the standardized return type from ACTUSDataProcessor)
   */
  private convertToACTUSResponse(
    processedData: ReturnType<typeof processRawACTUSData>
  ): ACTUSResponse {
    const { inflow, outflow, monthsCount, contractDetails } = processedData;

    // Aggregate cash flows for consistency
    const aggregatedInflows = inflow.map(period => period.reduce((sum, val) => sum + val, 0));
    const aggregatedOutflows = outflow.map(period => period.reduce((sum, val) => sum + val, 0));

    return {
      inflow: inflow,
      outflow: outflow,
      periodsCount: monthsCount,
      contractDetails: contractDetails,
      riskMetrics: {
        totalPeriods: monthsCount,
        aggregatedInflows,
        aggregatedOutflows
      },
      metadata: {
        timeHorizon: 'monthly',
        currency: 'USD',
        processingDate: new Date().toISOString()
      }
    };
  }

  // =================================== Portfolio Loading ===================================

  /**
   * Load portfolio from JSON file
   */
  static async loadPortfolio(portfolioPath: string): Promise<ACTUSContract[]> {
    try {
      const fs = await import('fs');
      const path = await import('path');

      const fullPath = path.resolve(portfolioPath);

      if (!fs.existsSync(fullPath)) {
        throw new Error(`Portfolio file not found: ${fullPath}`);
      }

      const fileContent = fs.readFileSync(fullPath, 'utf8');
      const portfolioConfig = JSON.parse(fileContent);

      if (!portfolioConfig.contracts || !Array.isArray(portfolioConfig.contracts)) {
        throw new Error('Invalid portfolio format: missing contracts array');
      }

      console.error(`📁 Loaded portfolio from: ${portfolioPath}`);
      if (portfolioConfig.portfolioMetadata) {
        console.error(`   Portfolio ID   : ${portfolioConfig.portfolioMetadata.portfolioId}`);
        console.error(`   Total Notional : ${portfolioConfig.portfolioMetadata.totalNotional}`);
        console.error(`   Currency       : ${portfolioConfig.portfolioMetadata.currency}`);
      }
      console.error(`   Contracts: ${portfolioConfig.contracts.length}`);

      return portfolioConfig.contracts;

    } catch (error: any) {
      console.error(`❌ Failed to load portfolio:`, error.message);
      throw error;
    }
  }
}