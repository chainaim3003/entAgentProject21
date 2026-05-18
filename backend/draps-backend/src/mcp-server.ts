import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { StableCoinVerifier } from "./verifier/StableCoinVerifier.js";
import type { VerificationParams } from "./types/index.js";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_ACTUS_URL = "http://34.203.247.32:8083/eventsBatch";
const DEFAULT_LOCAL_RISK_URL = "http://localhost:8082";
const DEFAULT_LOCAL_SIM_URL = "http://localhost:8083";
const DEFAULT_AWS_RISK_URL = "http://34.203.247.32:8082";
const DEFAULT_AWS_SIM_URL = "http://34.203.247.32:8083";

// ── Create MCP Server ─────────────────────────────────────────────
const server = new Server(
  { name: "generalRisk", version: "3.2.0" },
  { capabilities: { tools: {} } }
);

// ══════════════════════════════════════════════════════════════════
// LIST TOOLS
// ══════════════════════════════════════════════════════════════════
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // ─── Tool 1: verify_portfolio (UNCHANGED) ──────────────
      {
        name: "verify_portfolio",
        description:
          "Verify a stablecoin portfolio for risk compliance. Checks backing ratio, liquidity ratio, concentration risk, and asset quality against regulatory thresholds (EU MiCA or US GENIUS Act).",
        inputSchema: {
          type: "object",
          properties: {
            portfolio_json: {
              type: "string",
              description:
                "The portfolio as a JSON string. Must include a contracts array. Each contract needs: contractType, contractID, contractRole (RPA=asset RPL=liability), statusDate, notionalPrincipal, currency.",
            },
            backing_ratio_threshold: {
              type: "number",
              description: "Minimum backing ratio percentage (default: 100)",
              default: 100,
            },
            liquidity_ratio_threshold: {
              type: "number",
              description: "Minimum liquidity ratio percentage (default: 20)",
              default: 20,
            },
            concentration_limit: {
              type: "number",
              description: "Maximum concentration risk percentage (default: 40)",
              default: 40,
            },
            quality_threshold: {
              type: "number",
              description: "Minimum asset quality score 0-100 (default: 80)",
              default: 80,
            },
            actus_url: {
              type: "string",
              description: "ACTUS server URL. Leave empty to use default AWS server.",
            },
          },
          required: ["portfolio_json"],
        },
      },
      // ─── Tool 2: get_threshold_presets (UNCHANGED) ─────────
      {
        name: "get_threshold_presets",
        description:
          "Get the regulatory threshold presets for EU MiCA or US GENIUS Act stablecoin compliance frameworks.",
        inputSchema: {
          type: "object",
          properties: {
            jurisdiction: {
              type: "string",
              enum: ["eu-mica", "us-genius", "custom"],
              description: "Regulatory jurisdiction to get thresholds for",
            },
          },
          required: ["jurisdiction"],
        },
      },
      // ─── Tool 3: list_sample_portfolios (UNCHANGED) ────────
      {
        name: "list_sample_portfolios",
        description:
          "List all available sample portfolio and scenario files. Use returned filenames with load_sample_portfolio tool.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // ─── Tool 4: load_sample_portfolio (UNCHANGED) ─────────
      {
        name: "load_sample_portfolio",
        description:
          "Load a sample portfolio or test scenario file from the config directory. Returns portfolio JSON ready to pass into verify_portfolio.",
        inputSchema: {
          type: "object",
          properties: {
            filename: {
              type: "string",
              description:
                "The portfolio filename e.g. 'portfolio-balanced-1M.json' or 'scenario-balanced-compliant-10m.json'",
            },
          },
          required: ["filename"],
        },
      },
      // ─── Tool 5: run_simulation ────────────────────────────
      // UPDATED in v3.2.0: Now supports BOTH ACTUS endpoints:
      //   /eventsBatch         — for collections with inline riskFactors (supply chain tariff, SWAPS)
      //   /rf2/scenarioSimulation — for collections with pre-loaded scenarios (DeFi, hybrid treasury)
      // Auto-detects based on payload structure. No breaking changes.
      {
        name: "run_simulation",
        description: `Execute an ACTUS financial contract simulation against the ACTUS risk engine (ports 8082/8083 or AWS). This tool runs a complete multi-step workflow: loads market risk factors (interest rates, collateral/asset prices), configures risk models (prepayment, LTV monitoring, buffer protection, allocation drift, early settlement, penalty accrual), creates a scenario, and runs the ACTUS simulation engine.

SUPPORTS TWO ACTUS ENDPOINTS (auto-detected from payload):
  1. /eventsBatch — for collections with INLINE riskFactors (supply chain tariff, SWAPS collections)
  2. /rf2/scenarioSimulation — for collections with PRE-LOADED scenarios (DeFi, hybrid treasury, stablecoin)

Auto-detection: If simulation_json contains a top-level "riskFactors" array → routes to /eventsBatch.
If it contains "reference_indexes" + "scenario" → routes to /rf2/scenarioSimulation.

USE THIS TOOL WHEN the user asks to run or execute any simulation collection — DeFi liquidation, hybrid treasury, stablecoin, dynamic discounting, supply chain tariff, or any other ACTUS Postman collection.

INPUT: A JSON object containing all simulation components. All fields are OPTIONAL — omit any section to skip that step.

RESPONSE: Structured JSON with simulation_metadata, market_risk_factors loaded, scenario_config, simulation_results (per-contract event arrays from ACTUS), and analysis summary.`,
        inputSchema: {
          type: "object",
          properties: {
            simulation_json: {
              type: "string",
              description: "Complete simulation configuration as a JSON string. For /eventsBatch: include contracts and riskFactors (inline). For /rf2/scenarioSimulation: include reference_indexes, prepayment_models, buffer_ltv_models, collateral_ltv_models, scenario, contracts, and simulateTo.",
            },
            risk_server_url: {
              type: "string",
              description: "ACTUS risk factor server URL. If omitted, tries localhost:8082 first, then falls back to AWS (34.203.247.32:8082).",
            },
            simulation_server_url: {
              type: "string",
              description: "ACTUS simulation server URL. If omitted, tries localhost:8083 first, then falls back to AWS (34.203.247.32:8083).",
            },
          },
          required: ["simulation_json"],
        },
      },
      // ─── Tool 6: list_simulations (UNCHANGED) ─────────────
      {
        name: "list_simulations",
        description: "List all available simulation collections across all domains: defi-liquidation-collateral, hybrid-treasury, stablecoin, dynamic-discounting, supplychain-tariff, base-actus-samples. Returns filenames organized by domain and subcategory. Use load_simulation to read a specific file.",
        inputSchema: {
          type: "object",
          properties: {
            environment: {
              type: "string",
              enum: ["hosted", "local"],
              description: "Which environment to list from. 'hosted' = AWS server collections, 'local' = localhost Docker collections. Default: 'hosted'.",
            },
            domain: {
              type: "string",
              description: "Optional: filter to a specific domain. One of: defi-liquidation-collateral, hybrid-treasury, stablecoin, dynamic-discounting, supplychain-tariff, base-actus-samples. If omitted, lists all domains.",
            },
          },
          required: [],
        },
      },
      // ─── Tool 7: load_simulation (UNCHANGED) ──────────────
      {
        name: "load_simulation",
        description: "Load any simulation collection file from any domain. Returns the full Postman collection JSON including all API request bodies (reference indexes, risk models, scenario config, contracts, simulation params). Use list_simulations first to see available files.",
        inputSchema: {
          type: "object",
          properties: {
            filename: {
              type: "string",
              description: "The collection filename, e.g. 'ETH-Liq-LTV-Coll1-TPP-1week-hourly.json' or 'HT-CONS-time-1.json' or 'DynDisc-EarlySettlement-Linear-30d.json'",
            },
            domain: {
              type: "string",
              description: "The domain folder. One of: defi-liquidation-collateral, hybrid-treasury, stablecoin, dynamic-discounting, supplychain-tariff, base-actus-samples. If omitted, searches all domains.",
            },
            subcategory: {
              type: "string",
              description: "The subcategory folder within the domain, e.g. 'defi-liquidation-collateral-3' or 'hybrid-treasury-4' or 'stablecoin-1'. If omitted, searches all subcategories.",
            },
            environment: {
              type: "string",
              enum: ["hosted", "local"],
              description: "Which environment to load from. Default: 'hosted'.",
            },
          },
          required: ["filename"],
        },
      },
    ],
  };
});

// ══════════════════════════════════════════════════════════════════
// Helper: HTTP POST for ACTUS servers
// ══════════════════════════════════════════════════════════════════
async function actusPost(url: string, body: any): Promise<any> {
  const axios = (await import("axios")).default;
  const response = await axios.post(url, body, {
    headers: { "Content-Type": "application/json" },
    timeout: 60000,
  });
  return response.data;
}

// ══════════════════════════════════════════════════════════════════
// Helper: Quick health check — can we reach this server?
// ══════════════════════════════════════════════════════════════════
async function isServerReachable(baseUrl: string): Promise<boolean> {
  try {
    const axios = (await import("axios")).default;
    await axios.get(`${baseUrl}/findAllScenarios`, { timeout: 3000 });
    return true;
  } catch {
    return false;
  }
}

// ══════════════════════════════════════════════════════════════════
// Helper: Resolve server URLs — try localhost first, fallback to AWS
// Returns { riskUrl, simUrl, server_used } with full transparency
// ══════════════════════════════════════════════════════════════════
async function resolveServerUrls(
  explicitRiskUrl?: string,
  explicitSimUrl?: string
): Promise<{ riskUrl: string; simUrl: string; server_used: string }> {
  // If user explicitly passed URLs, use them — no fallback
  if (explicitRiskUrl || explicitSimUrl) {
    return {
      riskUrl: explicitRiskUrl || DEFAULT_LOCAL_RISK_URL,
      simUrl: explicitSimUrl || DEFAULT_LOCAL_SIM_URL,
      server_used: `explicit: risk=${explicitRiskUrl || DEFAULT_LOCAL_RISK_URL}, sim=${explicitSimUrl || DEFAULT_LOCAL_SIM_URL}`,
    };
  }

  // No explicit URLs — try localhost first
  const localAlive = await isServerReachable(DEFAULT_LOCAL_RISK_URL);
  if (localAlive) {
    return {
      riskUrl: DEFAULT_LOCAL_RISK_URL,
      simUrl: DEFAULT_LOCAL_SIM_URL,
      server_used: `localhost (Docker) — ${DEFAULT_LOCAL_RISK_URL} / ${DEFAULT_LOCAL_SIM_URL}`,
    };
  }

  // Localhost unreachable — try AWS
  const awsAlive = await isServerReachable(DEFAULT_AWS_RISK_URL);
  if (awsAlive) {
    return {
      riskUrl: DEFAULT_AWS_RISK_URL,
      simUrl: DEFAULT_AWS_SIM_URL,
      server_used: `AWS fallback — ${DEFAULT_AWS_RISK_URL} / ${DEFAULT_AWS_SIM_URL} (localhost was unreachable)`,
    };
  }

  // Both unreachable — return localhost URLs so the caller gets a clear connection error
  return {
    riskUrl: DEFAULT_LOCAL_RISK_URL,
    simUrl: DEFAULT_LOCAL_SIM_URL,
    server_used: "NONE — both localhost and AWS are unreachable",
  };
}

// ══════════════════════════════════════════════════════════════════
// Helper: Get simulation base path
// ══════════════════════════════════════════════════════════════════
function getSimulationBasePath(environment: string): string {
  return path.join(__dirname, "..", "config", "simulation", environment);
}

// ══════════════════════════════════════════════════════════════════
// CALL TOOL
// ══════════════════════════════════════════════════════════════════
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // ── TOOL 1: verify_portfolio (UNCHANGED) ──────────────────────
  if (name === "verify_portfolio") {
    try {
      const portfolioJson = args?.portfolio_json as string;
      if (!portfolioJson) {
        return { content: [{ type: "text", text: "Error: portfolio_json is required" }], isError: true };
      }

      const portfolioData = JSON.parse(portfolioJson);
      const portfolioConfig = {
        portfolioMetadata: {
          portfolioId: portfolioData.portfolioId || portfolioData.portfolioMetadata?.portfolioId || "MCP_PORTFOLIO",
          totalNotional: portfolioData.totalNotional || portfolioData.portfolioMetadata?.totalNotional || 0,
          currency: portfolioData.currency || portfolioData.portfolioMetadata?.currency || "USD",
        },
        contracts: portfolioData.contracts || [],
      };

      if (portfolioConfig.contracts.length === 0) {
        return { content: [{ type: "text", text: "Error: No contracts found. Please include a 'contracts' array." }], isError: true };
      }

      const tempPath = path.join(os.tmpdir(), `mcp-portfolio-${Date.now()}.json`);
      fs.writeFileSync(tempPath, JSON.stringify(portfolioConfig, null, 2));

      const params: VerificationParams = {
        backingRatioThreshold: (args?.backing_ratio_threshold as number) ?? 100,
        liquidityRatioThreshold: (args?.liquidity_ratio_threshold as number) ?? 20,
        concentrationLimit: (args?.concentration_limit as number) ?? 40,
        qualityThreshold: (args?.quality_threshold as number) ?? 80,
        actusUrl: (args?.actus_url as string) || DEFAULT_ACTUS_URL,
        portfolioPath: tempPath,
      };

      const verifier = new StableCoinVerifier();
      const result = await verifier.verify(params);
      try { fs.unlinkSync(tempPath); } catch { /* ignore */ }

      const summary = {
        compliant: result.compliant,
        overall_status: result.summary.overallStatus,
        periods_analyzed: result.summary.periodsAnalyzed,
        metrics: {
          backing_ratio: { value: `${result.riskMetrics.averageBackingRatio.toFixed(2)}%`, threshold: `${params.backingRatioThreshold}%`, status: result.summary.backing.status },
          liquidity_ratio: { value: `${result.riskMetrics.averageLiquidityRatio.toFixed(2)}%`, threshold: `${params.liquidityRatioThreshold}%`, status: result.summary.liquidity.status },
          concentration_risk: { value: `${result.riskMetrics.maxConcentrationRisk.toFixed(2)}%`, limit: `${params.concentrationLimit}%`, status: result.summary.concentration.status },
          asset_quality: { value: result.riskMetrics.averageAssetQuality.toFixed(2), threshold: params.qualityThreshold, status: result.summary.quality.status },
        },
        failure_reasons: result.summary.failureReasons,
        timestamp: result.timestamp,
      };
      return { content: [{ type: "text", text: JSON.stringify(summary, null, 2) }] };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Verification failed: ${msg}` }], isError: true };
    }
  }

  // ── TOOL 2: get_threshold_presets (UNCHANGED) ─────────────────
  if (name === "get_threshold_presets") {
    const jurisdiction = (args?.jurisdiction as string) || "custom";
    const presets: Record<string, object> = {
      "eu-mica": { backing_ratio: 100, liquidity_ratio: 30, concentration_limit: 60, asset_quality: 85, description: "EU Markets in Crypto-Assets (MiCA) regulation", notes: "Stricter liquidity requirement than US GENIUS Act" },
      "us-genius": { backing_ratio: 100, liquidity_ratio: 20, concentration_limit: 40, asset_quality: 80, description: "US GENIUS Act stablecoin framework", notes: "Default framework used in this system" },
      custom: { backing_ratio: 100, liquidity_ratio: 20, concentration_limit: 40, asset_quality: 80, description: "Default custom thresholds" },
    };
    return { content: [{ type: "text", text: JSON.stringify(presets[jurisdiction] ?? presets["custom"], null, 2) }] };
  }

  // ── TOOL 3: list_sample_portfolios (UNCHANGED) ────────────────
  if (name === "list_sample_portfolios") {
    try {
      const configPath = path.join(__dirname, "..", "config");
      const portfolioFiles = fs.existsSync(configPath) ? fs.readdirSync(configPath).filter((f) => f.startsWith("portfolio-") && f.endsWith(".json")) : [];
      const scenarioPath = path.join(configPath, "test-scenarios");
      const scenarioFiles = fs.existsSync(scenarioPath) ? fs.readdirSync(scenarioPath).filter((f) => f.endsWith(".json")) : [];
      return { content: [{ type: "text", text: JSON.stringify({ portfolios: portfolioFiles, test_scenarios: scenarioFiles, usage: "Pass any filename to load_sample_portfolio tool" }, null, 2) }] };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${msg}` }], isError: true };
    }
  }

  // ── TOOL 4: load_sample_portfolio (UNCHANGED) ─────────────────
  if (name === "load_sample_portfolio") {
    try {
      const filename = args?.filename as string;
      if (!filename) { return { content: [{ type: "text", text: "Error: filename is required" }], isError: true }; }
      const configPath = path.join(__dirname, "..", "config");
      let filePath = path.join(configPath, filename);
      if (!fs.existsSync(filePath)) { filePath = path.join(configPath, "test-scenarios", filename); }
      if (!fs.existsSync(filePath)) { return { content: [{ type: "text", text: `File not found: ${filename}. Use list_sample_portfolios to see available files.` }], isError: true }; }
      const content = fs.readFileSync(filePath, "utf-8");
      return { content: [{ type: "text", text: content }] };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${msg}` }], isError: true };
    }
  }

  // ══════════════════════════════════════════════════════════════
  // TOOL 5: run_simulation
  // v3.2.0: Added /eventsBatch path for supply chain tariff collections
  // ══════════════════════════════════════════════════════════════
  if (name === "run_simulation") {
    try {
      const simJsonStr = args?.simulation_json as string;
      if (!simJsonStr) { return { content: [{ type: "text", text: "Error: simulation_json is required" }], isError: true }; }

      const simConfig = JSON.parse(simJsonStr);

      // ── Resolve server URLs: localhost first, AWS fallback, full transparency ──
      const { riskUrl, simUrl, server_used } = await resolveServerUrls(
        args?.risk_server_url as string | undefined,
        args?.simulation_server_url as string | undefined
      );

      // ════════════════════════════════════════════════════════
      // PATH A: /eventsBatch — inline riskFactors
      // Used by: supply chain tariff, SWAPS collections
      // Detect: payload has top-level "riskFactors" array
      // ════════════════════════════════════════════════════════
      if (simConfig.riskFactors && Array.isArray(simConfig.riskFactors)) {
        if (!simConfig.contracts || !Array.isArray(simConfig.contracts) || simConfig.contracts.length === 0) {
          return { content: [{ type: "text", text: "Error: 'contracts' array is required in simulation_json" }], isError: true };
        }

        const eventsBatchPayload = {
          contracts: simConfig.contracts,
          riskFactors: simConfig.riskFactors,
        };

        let ebResponse: any;
        const endpoint = `${simUrl}/eventsBatch`;
        try {
          ebResponse = await actusPost(endpoint, eventsBatchPayload);
        } catch (err: any) {
          return { content: [{ type: "text", text: JSON.stringify({
            error: `eventsBatch simulation failed: ${err.message}`,
            endpoint_used: endpoint,
            server_used,
            contracts_sent: simConfig.contracts.length,
            risk_factors_sent: simConfig.riskFactors.length,
            hint: "Ensure ACTUS server is running on port 8083 and accepts /eventsBatch",
          }, null, 2) }], isError: true };
        }

        // Analyze results
        const analysis: any = { total_events: 0, event_counts_by_type: {}, rate_summary: {}, loan_summary: {} };
        const contractResults: any[] = [];

        if (Array.isArray(ebResponse)) {
          for (const contractResult of ebResponse) {
            const events = contractResult.events || [];
            analysis.total_events += events.length;
            for (const evt of events) {
              analysis.event_counts_by_type[evt.type] = (analysis.event_counts_by_type[evt.type] || 0) + 1;
            }
            const ipEvents = events.filter((e: any) => e.type === "IP");
            let totalIP = 0;
            for (const ip of ipEvents) { totalIP += ip.payoff || 0; }
            const rrEvents = events.filter((e: any) => e.type === "RR");
            if (rrEvents.length > 0) {
              let minRate = Infinity, maxRate = -Infinity, minTime = "", maxTime = "";
              for (const rr of rrEvents) {
                if (rr.nominalRate < minRate) { minRate = rr.nominalRate; minTime = rr.time; }
                if (rr.nominalRate > maxRate) { maxRate = rr.nominalRate; maxTime = rr.time; }
              }
              analysis.rate_summary[contractResult.contractId || contractResult.contractID || "unknown"] = {
                initial: rrEvents[0].nominalRate, min: minRate, max: maxRate,
                final: rrEvents[rrEvents.length - 1].nominalRate,
                min_time: minTime, max_time: maxTime, total_resets: rrEvents.length,
              };
            }
            contractResults.push({
              contractId: contractResult.contractId || contractResult.contractID,
              status: contractResult.status,
              events_count: events.length,
              ip_total: totalIP,
              events: events,
            });
          }
        }

        const finalResponse = {
          simulation_metadata: {
            endpoint_used: endpoint,
            endpoint_mode: "eventsBatch",
            contracts_count: simConfig.contracts.length,
            risk_factors_count: simConfig.riskFactors.length,
            timestamp: new Date().toISOString(),
            server_used: server_used,
          },
          simulation_results: contractResults,
          analysis: analysis,
        };
        return { content: [{ type: "text", text: JSON.stringify(finalResponse, null, 2) }] };
      }

      // ════════════════════════════════════════════════════════
      // PATH B: /rf2/scenarioSimulation — pre-loaded scenarios
      // Used by: DeFi, hybrid treasury, stablecoin, dynamic discounting
      // Everything below is UNCHANGED from v3.1.0
      // ════════════════════════════════════════════════════════
      const loadResults: any = { reference_indexes: [], prepayment_models: [], ltv_models: [] };

      // Step 1: Load reference indexes
      if (simConfig.reference_indexes && Array.isArray(simConfig.reference_indexes)) {
        for (const idx of simConfig.reference_indexes) {
          try {
            const result = await actusPost(`${riskUrl}/addReferenceIndex`, idx);
            loadResults.reference_indexes.push({ riskFactorID: idx.riskFactorID, marketObjectCode: idx.marketObjectCode, data_points: idx.data?.length || 0, status: "loaded", server_response: typeof result === "string" ? result.trim() : result });
          } catch (err: any) { loadResults.reference_indexes.push({ riskFactorID: idx.riskFactorID, status: "error", error: err.message }); }
        }
      }

      // Step 2: Load prepayment models
      if (simConfig.prepayment_models && Array.isArray(simConfig.prepayment_models)) {
        for (const pm of simConfig.prepayment_models) {
          try {
            const result = await actusPost(`${riskUrl}/addTwoDimensionalPrepaymentModel`, pm);
            loadResults.prepayment_models.push({ riskFactorId: pm.riskFactorId, evaluation_times: pm.prepaymentEventTimes?.length || 0, status: "loaded", server_response: typeof result === "string" ? result.trim() : result });
          } catch (err: any) { loadResults.prepayment_models.push({ riskFactorId: pm.riskFactorId, status: "error", error: err.message }); }
        }
      }

      // Step 3: Load buffer LTV models
      if (simConfig.buffer_ltv_models && Array.isArray(simConfig.buffer_ltv_models)) {
        for (const bm of simConfig.buffer_ltv_models) {
          try {
            const result = await actusPost(`${riskUrl}/addBufferLTVModel`, bm);
            loadResults.ltv_models.push({ riskFactorId: bm.riskFactorId, type: "BufferLTVModel", collateral_quantity: bm.collateralQuantity, buffer_quantity: bm.initialBufferQuantity, ltv_threshold: bm.ltvThreshold, liquidation_threshold: bm.liquidationThreshold, monitoring_points: bm.monitoringEventTimes?.length || 0, status: "loaded", server_response: typeof result === "string" ? result.trim() : result });
          } catch (err: any) { loadResults.ltv_models.push({ riskFactorId: bm.riskFactorId, type: "BufferLTVModel", status: "error", error: err.message }); }
        }
      }

      // Step 3b: Load collateral LTV models
      if (simConfig.collateral_ltv_models && Array.isArray(simConfig.collateral_ltv_models)) {
        for (const cm of simConfig.collateral_ltv_models) {
          try {
            const result = await actusPost(`${riskUrl}/addCollateralLTVModel`, cm);
            loadResults.ltv_models.push({ riskFactorId: cm.riskFactorId, type: "CollateralLTVModel", collateral_quantity: cm.collateralQuantity, ltv_threshold: cm.ltvThreshold, monitoring_points: cm.monitoringEventTimes?.length || 0, status: "loaded", server_response: typeof result === "string" ? result.trim() : result });
          } catch (err: any) { loadResults.ltv_models.push({ riskFactorId: cm.riskFactorId, type: "CollateralLTVModel", status: "error", error: err.message }); }
        }
      }

      // Step 4: Create scenario
      let scenarioResult: any = null;
      if (simConfig.scenario) {
        try {
          const result = await actusPost(`${riskUrl}/addScenario`, simConfig.scenario);
          scenarioResult = { scenarioID: simConfig.scenario.scenarioID, risk_factors_count: simConfig.scenario.riskFactorDescriptors?.length || 0, status: "created", server_response: typeof result === "string" ? result.trim() : result };
        } catch (err: any) { scenarioResult = { scenarioID: simConfig.scenario.scenarioID, status: "error", error: err.message }; }
      }

      // Step 5: Run simulation via /rf2/scenarioSimulation
      if (!simConfig.contracts || !Array.isArray(simConfig.contracts) || simConfig.contracts.length === 0) {
        return { content: [{ type: "text", text: "Error: 'contracts' array is required in simulation_json" }], isError: true };
      }
      if (!simConfig.simulateTo) {
        return { content: [{ type: "text", text: "Error: 'simulateTo' date is required in simulation_json" }], isError: true };
      }

      const simulationRequest = {
        contracts: simConfig.contracts,
        scenarioDescriptor: simConfig.scenario ? { scenarioID: simConfig.scenario.scenarioID, scenarioType: "scenario" } : undefined,
        simulateTo: simConfig.simulateTo,
        monitoringTimes: simConfig.monitoringTimes || [],
      };

      let simulationResponse: any;
      try {
        simulationResponse = await actusPost(`${simUrl}/rf2/scenarioSimulation`, simulationRequest);
      } catch (err: any) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Simulation execution failed: ${err.message}`, market_risk_factors: loadResults, scenario_config: scenarioResult, hint: "Ensure ACTUS servers are running on ports 8082 and 8083" }, null, 2) }], isError: true };
      }

      // Step 6: Analyze results
      const analysis: any = { total_events: 0, event_counts_by_type: {}, interventions: [], rate_summary: {}, loan_summary: {}, collateral_preserved: true };
      const contractResults: any[] = [];

      if (Array.isArray(simulationResponse)) {
        for (const contractResult of simulationResponse) {
          const events = contractResult.events || [];
          analysis.total_events += events.length;
          for (const evt of events) { analysis.event_counts_by_type[evt.type] = (analysis.event_counts_by_type[evt.type] || 0) + 1; }
          const ppEvents = events.filter((e: any) => e.type === "PP");
          for (const pp of ppEvents) { analysis.interventions.push({ time: pp.time, payoff: pp.payoff, notional_after: pp.nominalValue, rate_at_time: pp.nominalRate }); }
          const rrEvents = events.filter((e: any) => e.type === "RR");
          if (rrEvents.length > 0) {
            let minRate = Infinity, maxRate = -Infinity, minTime = "", maxTime = "";
            for (const rr of rrEvents) { if (rr.nominalRate < minRate) { minRate = rr.nominalRate; minTime = rr.time; } if (rr.nominalRate > maxRate) { maxRate = rr.nominalRate; maxTime = rr.time; } }
            analysis.rate_summary = { initial: rrEvents[0].nominalRate, min: minRate, max: maxRate, final: rrEvents[rrEvents.length - 1].nominalRate, min_time: minTime, max_time: maxTime, total_resets: rrEvents.length };
          }
          const iedEvent = events.find((e: any) => e.type === "IED");
          const mdEvent = events.find((e: any) => e.type === "MD");
          if (iedEvent) {
            const initialNotional = Math.abs(iedEvent.nominalValue || iedEvent.payoff || 0);
            const finalNotional = mdEvent ? Math.abs(mdEvent.payoff || mdEvent.nominalValue || 0) : initialNotional;
            const totalPrepaid = ppEvents.reduce((sum: number, pp: any) => sum + Math.abs(pp.payoff || 0), 0);
            analysis.loan_summary = { initial_notional: initialNotional, final_notional: finalNotional, total_prepaid: totalPrepaid, total_deleveraged_pct: initialNotional > 0 ? parseFloat(((totalPrepaid / initialNotional) * 100).toFixed(2)) : 0 };
          }
          contractResults.push({ contractId: contractResult.contractId || contractResult.contractID, status: contractResult.status, events_count: events.length, events: events });
        }
      }

      const finalResponse = {
        simulation_metadata: { endpoint_used: `${simUrl}/rf2/scenarioSimulation`, endpoint_mode: "scenarioSimulation", scenario_id: simConfig.scenario?.scenarioID || "none", contracts_count: simConfig.contracts.length, simulate_to: simConfig.simulateTo, timestamp: new Date().toISOString(), server_used: server_used },
        market_risk_factors: loadResults,
        scenario_config: scenarioResult,
        contracts: simConfig.contracts.map((c: any) => ({ contractID: c.contractID, contractType: c.contractType, contractRole: c.contractRole, notionalPrincipal: c.notionalPrincipal, currency: c.currency, maturityDate: c.maturityDate, prepaymentModels: c.prepaymentModels })),
        simulation_results: contractResults,
        analysis: analysis,
      };
      return { content: [{ type: "text", text: JSON.stringify(finalResponse, null, 2) }] };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Simulation failed: ${msg}` }], isError: true };
    }
  }

  // ══════════════════════════════════════════════════════════════
  // TOOL 6: list_simulations (UNCHANGED)
  // ══════════════════════════════════════════════════════════════
  if (name === "list_simulations") {
    try {
      const environment = (args?.environment as string) || "hosted";
      const filterDomain = args?.domain as string;

      const basePath = getSimulationBasePath(environment);
      const result: Record<string, Record<string, string[]>> = {};

      if (!fs.existsSync(basePath)) {
        return { content: [{ type: "text", text: JSON.stringify({ error: `Environment directory not found: ${basePath}`, available_environments: ["hosted", "local"] }, null, 2) }], isError: true };
      }

      const domains = fs.readdirSync(basePath).filter((d) => {
        const full = path.join(basePath, d);
        if (!fs.statSync(full).isDirectory()) return false;
        if (filterDomain && d !== filterDomain) return false;
        return true;
      });

      for (const domain of domains) {
        const domainPath = path.join(basePath, domain);
        result[domain] = {};

        const directFiles = fs.readdirSync(domainPath).filter((f) => f.endsWith(".json"));
        if (directFiles.length > 0) {
          result[domain]["_root"] = directFiles;
        }

        const subcategories = fs.readdirSync(domainPath).filter((d) => {
          const full = path.join(domainPath, d);
          return fs.statSync(full).isDirectory();
        });

        for (const sub of subcategories) {
          const subPath = path.join(domainPath, sub);
          const files = fs.readdirSync(subPath).filter((f) => f.endsWith(".json"));
          if (files.length > 0) {
            result[domain][sub] = files;
          }
        }

        if (Object.keys(result[domain]).length === 0) {
          delete result[domain];
        }
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            environment,
            domains: result,
            usage: "Pass filename (and optionally domain + subcategory) to load_simulation",
          }, null, 2),
        }],
      };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${msg}` }], isError: true };
    }
  }

  // ══════════════════════════════════════════════════════════════
  // TOOL 7: load_simulation (UNCHANGED)
  // ══════════════════════════════════════════════════════════════
  if (name === "load_simulation") {
    try {
      const filename = args?.filename as string;
      if (!filename) { return { content: [{ type: "text", text: "Error: filename is required" }], isError: true }; }

      const environment = (args?.environment as string) || "hosted";
      const filterDomain = args?.domain as string;
      const filterSubcategory = args?.subcategory as string;

      const basePath = getSimulationBasePath(environment);
      let filePath = "";

      if (filterDomain && filterSubcategory) {
        filePath = path.join(basePath, filterDomain, filterSubcategory, filename);
      } else if (filterDomain) {
        const domainPath = path.join(basePath, filterDomain);
        if (fs.existsSync(domainPath)) {
          const rootCandidate = path.join(domainPath, filename);
          if (fs.existsSync(rootCandidate)) {
            filePath = rootCandidate;
          } else {
            const subs = fs.readdirSync(domainPath).filter((d) => fs.statSync(path.join(domainPath, d)).isDirectory());
            for (const sub of subs) {
              const candidate = path.join(domainPath, sub, filename);
              if (fs.existsSync(candidate)) { filePath = candidate; break; }
            }
          }
        }
      } else {
        if (fs.existsSync(basePath)) {
          const domains = fs.readdirSync(basePath).filter((d) => fs.statSync(path.join(basePath, d)).isDirectory());
          let found = false;
          for (const domain of domains) {
            if (found) break;
            const domainPath = path.join(basePath, domain);
            const rootCandidate = path.join(domainPath, filename);
            if (fs.existsSync(rootCandidate)) { filePath = rootCandidate; found = true; break; }
            const subs = fs.readdirSync(domainPath).filter((d) => fs.statSync(path.join(domainPath, d)).isDirectory());
            for (const sub of subs) {
              const candidate = path.join(domainPath, sub, filename);
              if (fs.existsSync(candidate)) { filePath = candidate; found = true; break; }
            }
          }
        }
      }

      if (!filePath || !fs.existsSync(filePath)) {
        return { content: [{ type: "text", text: `File not found: ${filename}. Use list_simulations to see available files.` }], isError: true };
      }

      const content = fs.readFileSync(filePath, "utf-8");
      return { content: [{ type: "text", text: content }] };
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error);
      return { content: [{ type: "text", text: `Error: ${msg}` }], isError: true };
    }
  }

  return { content: [{ type: "text", text: `Unknown tool: ${name}` }], isError: true };
});

// ══════════════════════════════════════════════════════════════════
// Start server
// ══════════════════════════════════════════════════════════════════
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("generalRisk MCP Server v3.2.0 started — localhost-first with AWS fallback, eventsBatch support");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});