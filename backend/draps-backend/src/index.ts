#!/usr/bin/env node

/**
 * RiskStableCoin Verifier - CLI Entry Point
 * Simplified stablecoin verification without ZK or Network components
 */

import { Command } from 'commander';
import { StableCoinVerifier } from './verifier/StableCoinVerifier.js';
import { displaySummary } from './utils/validation.js';
import type { VerificationParams } from './types/index.js';

const program = new Command();

program
  .name('risk-stablecoin-verifier')
  .description('Verify stablecoin liquidity, backing ratio, and compliance metrics')
  .version('1.0.0')
  .requiredOption('--backingRatio <number>', 'Backing ratio threshold (e.g., 100 for 100%)', parseFloat)
  .requiredOption('--liquidityRatio <number>', 'Liquidity ratio threshold (e.g., 20 for 20%)', parseFloat)
  .requiredOption('--concentrationLimit <number>', 'Concentration limit (e.g., 25 for 25%)', parseFloat)
  .requiredOption('--qualityThreshold <number>', 'Asset quality threshold (e.g., 80)', parseFloat)
  .requiredOption('--actusUrl <url>', 'ACTUS server URL (e.g., http://localhost:8083/eventsBatch)')
  .requiredOption('--portfolio <path>', 'Path to portfolio JSON file')
  .parse(process.argv);

const options = program.opts();

async function main() {
  try {
    // Validate parameters
    if (options.backingRatio <= 0) {
      console.error('❌ Error: Backing ratio must be positive');
      process.exit(1);
    }

    if (options.liquidityRatio < 0) {
      console.error('❌ Error: Liquidity ratio cannot be negative');
      process.exit(1);
    }

    if (options.concentrationLimit <= 0 || options.concentrationLimit > 100) {
      console.error('❌ Error: Concentration limit must be between 0 and 100');
      process.exit(1);
    }

    if (options.qualityThreshold < 0 || options.qualityThreshold > 100) {
      console.error('❌ Error: Quality threshold must be between 0 and 100');
      process.exit(1);
    }

    // Build verification parameters
    const params: VerificationParams = {
      backingRatioThreshold: options.backingRatio,
      liquidityRatioThreshold: options.liquidityRatio,
      concentrationLimit: options.concentrationLimit,
      qualityThreshold: options.qualityThreshold,
      actusUrl: options.actusUrl,
      portfolioPath: options.portfolio
    };

    // Execute verification
    const verifier = new StableCoinVerifier();
    const result = await verifier.verify(params);

    // Display results
    displaySummary(result.summary);

    // Exit with appropriate code
    if (result.compliant) {
      console.log('✅ Verification completed successfully - Portfolio is COMPLIANT\n');
      process.exit(0);
    } else {
      console.log('⚠️  Verification completed - Portfolio is NON-COMPLIANT\n');
      process.exit(1);
    }

  } catch (error: any) {
    console.error('\n💥 Fatal error:', error.message);
    if (error.stack) {
      console.error('\nStack trace:');
      console.error(error.stack);
    }
    process.exit(1);
  }
}

main();
