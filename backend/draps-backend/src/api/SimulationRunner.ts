// /**
//  * SimulationRunner
//  * ================
//  * Parses Postman collection JSONs from config/stimulation/ and executes
//  * the full ACTUS pipeline: load risk factors (8082) → run simulation (8083).
//  *
//  * Each Postman collection has items that are sequential API calls.
//  * This runner extracts method, path, and body from each item,
//  * replaces the host with the correct environment URL, and executes them.
//  */

// import axios from 'axios';

// // ── Types ────────────────────────────────────────────────────────────

// /** Result of a single step in the pipeline */
// export interface StepResult {
//   step: number;
//   name: string;
//   method: string;
//   url: string;
//   status: 'success' | 'failed';
//   httpStatus?: number;
//   response?: any;
//   error?: string;
//   durationMs: number;
// }

// /** Final result returned to the UI */
// export interface StimulationResult {
//   success: boolean;
//   scenarioName: string;
//   description: string;
//   environment: string;
//   riskServiceUrl: string;
//   actusServerUrl: string;
//   steps: StepResult[];
//   simulation: any | null;
//   totalDurationMs: number;
//   timestamp: string;
// }

// /** Environment URL configuration */
// export interface EnvironmentConfig {
//   riskServiceBase: string;   // e.g. http://localhost:8082
//   actusServerBase: string;   // e.g. http://localhost:8083
// }

// // ── Predefined environments ─────────────────────────────────────────

// export const ENVIRONMENTS: Record<string, EnvironmentConfig> = {
//   localhost: {
//     riskServiceBase: 'http://localhost:8082',
//     actusServerBase: 'http://localhost:8083',
//   },
//   aws: {
//     riskServiceBase: 'http://34.203.247.32:8082',
//     actusServerBase: 'http://34.203.247.32:8083',
//   },
// };

// // ── Postman collection parsing ──────────────────────────────────────

// /**
//  * Extract the URL path from a Postman URL object.
//  * Postman stores URLs as either a raw string or a structured object
//  * with host and path arrays.
//  */
// function extractPathFromPostmanUrl(urlObj: any): { port: string; path: string } {
//   if (typeof urlObj === 'string') {
//     const parsed = new URL(urlObj);
//     return { port: parsed.port, path: parsed.pathname };
//   }
//   // Structured Postman URL: { raw, protocol, host: ["localhost:8082"], path: ["addReferenceIndex"] }
//   const raw: string = urlObj.raw || '';
//   const parsed = new URL(raw);
//   return { port: parsed.port, path: parsed.pathname };
// }

// /**
//  * Given a Postman port (8082 or 8083), return the correct base URL
//  * for the chosen environment.
//  */
// function resolveBaseUrl(port: string, env: EnvironmentConfig): string {
//   if (port === '8083') return env.actusServerBase;
//   return env.riskServiceBase; // default to 8082
// }

// // ── Main runner ─────────────────────────────────────────────────────

// /**
//  * Execute all steps from a parsed Postman collection JSON.
//  *
//  * @param collectionJson - The full parsed JSON of a Postman collection
//  * @param env            - The environment config to use
//  * @returns StimulationResult with all step outcomes and the final simulation
//  */
// export async function runStimulation(
//   collectionJson: any,
//   env: EnvironmentConfig,
//   envName: string
// ): Promise<StimulationResult> {
//   const startTime = Date.now();
//   const items: any[] = collectionJson.item || [];
//   const info = collectionJson.info || {};
//   const steps: StepResult[] = [];
//   let simulation: any = null;
//   let allSuccess = true;

//   console.log(`\n🚀 SimulationRunner: ${info.name || 'Unknown'}`);
//   console.log(`   Environment: ${envName}`);
//   console.log(`   Risk Service: ${env.riskServiceBase}`);
//   console.log(`   ACTUS Server: ${env.actusServerBase}`);
//   console.log(`   Steps: ${items.length}`);
//   console.log('─'.repeat(60));

//   for (let i = 0; i < items.length; i++) {
//     const item = items[i];
//     const request = item.request;
//     if (!request) {
//       console.warn(`   ⚠️  Step ${i + 1}: no request object, skipping`);
//       continue;
//     }

//     const method: string = (request.method || 'GET').toUpperCase();
//     const { port, path } = extractPathFromPostmanUrl(request.url);
//     const baseUrl = resolveBaseUrl(port, env);
//     const fullUrl = `${baseUrl}${path}`;

//     // Extract body for POST requests
//     let body: any = undefined;
//     if (request.body && request.body.raw) {
//       try {
//         body = JSON.parse(request.body.raw);
//       } catch {
//         body = request.body.raw;
//       }
//     }

//     const stepStart = Date.now();
//     console.log(`   Step ${i + 1}/${items.length}: ${method} ${fullUrl}`);

//     try {
//       const response = await axios({
//         method: method.toLowerCase() as any,
//         url: fullUrl,
//         data: body,
//         headers: { 'Content-Type': 'application/json' },
//         timeout: 30000,
//       });

//       const stepResult: StepResult = {
//         step: i + 1,
//         name: item.name || `Step ${i + 1}`,
//         method,
//         url: fullUrl,
//         status: 'success',
//         httpStatus: response.status,
//         response: response.data,
//         durationMs: Date.now() - stepStart,
//       };

//       steps.push(stepResult);
//       console.log(`   ✅ ${response.status} (${stepResult.durationMs}ms)`);

//       // The last POST to 8083 is the simulation — capture it
//       if (port === '8083' && method === 'POST') {
//         simulation = response.data;
//       }
//     } catch (error: any) {
//       allSuccess = false;
//       const stepResult: StepResult = {
//         step: i + 1,
//         name: item.name || `Step ${i + 1}`,
//         method,
//         url: fullUrl,
//         status: 'failed',
//         httpStatus: error.response?.status,
//         error: error.message,
//         durationMs: Date.now() - stepStart,
//       };

//       steps.push(stepResult);
//       console.error(`   ❌ FAILED: ${error.message}`);

//       // If a setup step fails, stop — simulation won't work
//       if (port === '8082') {
//         console.error(`   🛑 Risk service step failed. Aborting remaining steps.`);
//         break;
//       }
//     }
//   }

//   const totalDurationMs = Date.now() - startTime;
//   console.log('─'.repeat(60));
//   console.log(`   Total: ${totalDurationMs}ms | Steps: ${steps.length}/${items.length} | Success: ${allSuccess}`);
//   if (simulation) {
//     const eventCount = simulation?.[0]?.events?.length ?? 0;
//     console.log(`   Simulation events: ${eventCount}`);
//   }
//   console.log('');

//   return {
//     success: allSuccess && simulation !== null,
//     scenarioName: info.name || 'Unknown',
//     description: info.description || '',
//     environment: envName,
//     riskServiceUrl: env.riskServiceBase,
//     actusServerUrl: env.actusServerBase,
//     steps,
//     simulation,
//     totalDurationMs,
//     timestamp: new Date().toISOString(),
//   };
// }


/**
 * SimulationRunner
 * =================
 * Executes Postman collection JSONs against the ACTUS pipeline.
 *
 * Two execution modes, selected automatically:
 *
 *   SIMPLE   – plain HTTP request chains (original behaviour, fully preserved)
 *              Triggered when: no nested folders, no prerequest/test scripts
 *
 *   SCRIPTED – full Postman-compatible runner with:
 *              • Recursive folder flattening
 *              • {{variable}} substitution from collection + environment vars
 *              • prerequest and test script execution via Node.js vm sandbox
 *              • pm.environment / pm.collectionVariables / pm.sendRequest
 *              • postman.setNextRequest() for loop control (epoch evaluator)
 *              Triggered when: collection has folders or event scripts
 *
 * Only SimulationRunner.ts changes. server.ts, types, and all other files
 * are untouched. The returned SimulationResult shape is identical for both modes.
 */

import { runInNewContext } from 'vm';
import axios from 'axios';

// ── Public types (interface unchanged) ──────────────────────────────

/** Result of a single step in the pipeline */
export interface StepResult {
  step: number;
  name: string;
  method: string;
  url: string;
  status: 'success' | 'failed';
  httpStatus?: number;
  response?: any;
  error?: string;
  durationMs: number;
}

/** A single time-series data point for a risk factor input */
export interface RiskFactorPoint {
  time: string;
  value: number;
}

/** Final result returned to the UI */
export interface StimulationResult {
  success: boolean;
  scenarioName: string;
  description: string;
  environment: string;
  riskServiceUrl: string;
  actusServerUrl: string;
  steps: StepResult[];
  simulation: any | null;
  /** Risk factor input time-series extracted from addReferenceIndex steps */
  riskFactorData: Record<string, RiskFactorPoint[]> | null;
  /** Final pm.environment snapshot. Test scripts in scripted collections
   *  use pm.environment.set() to publish per-scenario totals (A_total,
   *  B_total, C_total etc.). Empty in SIMPLE mode. */
  environmentVariables?: Record<string, string>;
  totalDurationMs: number;
  timestamp: string;
}

/** Environment URL configuration */
export interface EnvironmentConfig {
  riskServiceBase: string;
  actusServerBase: string;
}

// ── Predefined environments (unchanged) ─────────────────────────────

export const ENVIRONMENTS: Record<string, EnvironmentConfig> = {
  localhost: {
    riskServiceBase: 'http://localhost:8082',
    actusServerBase: 'http://localhost:8083',
  },
  aws: {
    riskServiceBase: 'http://34.203.247.32:8082',
    actusServerBase: 'http://34.203.247.32:8083',
  },
};

// ═══════════════════════════════════════════════════════════════════
// SECTION 1 – SHARED UTILITIES
// ═══════════════════════════════════════════════════════════════════

/**
 * Detect whether a collection needs the scripted runner.
 * One pass over top-level items is enough: if any item is a folder
 * (has nested item array) or has event scripts, scripted mode is used.
 */
function isScriptedCollection(collectionJson: any): boolean {
  const items: any[] = collectionJson.item || [];
  for (const item of items) {
    if (item.item && Array.isArray(item.item)) return true;
    if (Array.isArray(item.event) && item.event.length > 0) return true;
  }
  return false;
}

/**
 * Replace all {{varName}} tokens using the provided variable map.
 * Unresolved tokens are left as-is so they appear clearly in logs.
 */
function substituteVars(text: string, vars: Record<string, string>): string {
  return text.replace(/\{\{([^}]+)\}\}/g, (_match: string, key: string) => {
    const k = key.trim();
    return Object.prototype.hasOwnProperty.call(vars, k) ? vars[k] : `{{${k}}}`;
  });
}

/**
 * Extract port and pathname from a Postman URL (string or structured object).
 * Used only by the simple runner.
 */
function extractPathFromPostmanUrl(urlObj: any): { port: string; path: string } {
  const raw: string = typeof urlObj === 'string' ? urlObj : (urlObj?.raw || '');
  const parsed = new URL(raw);
  return { port: parsed.port, path: parsed.pathname };
}

/**
 * Map a Postman port to the correct environment base URL.
 * Used only by the simple runner.
 */
function resolveBaseUrl(port: string, env: EnvironmentConfig): string {
  return port === '8083' ? env.actusServerBase : env.riskServiceBase;
}

/**
 * Extract risk factor input time-series from collection request bodies.
 * Scans all items (recursively for folders) for POST requests to /addReferenceIndex
 * and parses the body to get marketObjectCode and data array.
 */
function extractRiskFactorInputs(
  collectionJson: any,
): Record<string, RiskFactorPoint[]> {
  const result: Record<string, RiskFactorPoint[]> = {};

  function scanItems(items: any[]): void {
    for (const item of items) {
      // Recurse into folders
      if (item.item && Array.isArray(item.item)) {
        scanItems(item.item);
        continue;
      }
      const req = item.request;
      if (!req || String(req.method || '').toUpperCase() !== 'POST') continue;

      // Check if this is an addReferenceIndex call
      const rawUrl: string =
        typeof req.url === 'string' ? req.url : String(req.url?.raw || '');
      if (!rawUrl.includes('addReferenceIndex')) continue;

      // Parse the request body
      if (!req.body?.raw) continue;
      try {
        const body = JSON.parse(String(req.body.raw));
        const moc: string = body.marketObjectCode;
        const data: Array<{ time: string; value: number }> = body.data;
        if (moc && Array.isArray(data) && data.length > 0) {
          result[moc] = data.map((d) => ({
            time: String(d.time),
            value: Number(d.value),
          }));
        }
      } catch {
        // Skip unparseable bodies
      }
    }
  }

  scanItems(collectionJson.item || []);
  return result;
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 2 – SCRIPTED RUNNER: pm.expect() ASSERTION BUILDER
// ═══════════════════════════════════════════════════════════════════

/**
 * Minimal chai-compatible expect() builder.
 * Implements only the assertions used in Approach3-style collections:
 *   pm.expect(v).to.be.oneOf([...])
 *   pm.expect(v).to.be.above(n)
 *   pm.expect(v).to.not.be.empty
 *   pm.expect(v).to.equal(x)
 */
function createExpect(value: unknown): unknown {
  function assert(condition: boolean, msg: string): void {
    if (!condition) throw new Error(`Assertion failed: ${msg}`);
  }

  function buildBe(negate: boolean): Record<string, unknown> {
    const q = negate ? ' not' : '';

    const be: Record<string, unknown> = {
      oneOf: (arr: unknown[]): void =>
        assert(
          negate ? !arr.includes(value) : arr.includes(value),
          `${JSON.stringify(value)} to${q} be one of [${arr}]`,
        ),
      above: (n: number): void =>
        assert(
          negate ? Number(value) <= n : Number(value) > n,
          `${String(value)} to${q} be above ${n}`,
        ),
      equal: (expected: unknown): void =>
        assert(
          negate ? value !== expected : value === expected,
          `${JSON.stringify(value)} to${q} equal ${JSON.stringify(expected)}`,
        ),
      at: {
        most: (n: number): void =>
          assert(
            negate ? Number(value) > n : Number(value) <= n,
            `${String(value)} to${q} be at most ${n}`,
          ),
        least: (n: number): void =>
          assert(
            negate ? Number(value) < n : Number(value) >= n,
            `${String(value)} to${q} be at least ${n}`,
          ),
      },
      within: (low: number, high: number): void =>
        assert(
          negate
            ? Number(value) < low || Number(value) > high
            : Number(value) >= low && Number(value) <= high,
          `${String(value)} to${q} be within ${low}..${high}`,
        ),
    };

    // .empty is a property getter, not a method (chai-style)
    Object.defineProperty(be, 'empty', {
      get(): void {
        const isEmpty =
          value === null ||
          value === undefined ||
          (typeof value === 'string' && value.length === 0) ||
          (Array.isArray(value) && value.length === 0);
        assert(
          negate ? !isEmpty : isEmpty,
          `${JSON.stringify(value)} to${q} be empty`,
        );
      },
      enumerable: true,
    });

    return be;
  }

  return {
    to: {
      be: buildBe(false),
      equal: (expected: unknown): void =>
        assert(
          value === expected,
          `${JSON.stringify(value)} to equal ${JSON.stringify(expected)}`,
        ),
      // .to.eql() — deep equality (used in verify steps)
      eql: (expected: unknown): void =>
        assert(
          JSON.stringify(value) === JSON.stringify(expected),
          `${JSON.stringify(value)} to eql ${JSON.stringify(expected)}`,
        ),
      // .to.include() — substring or array inclusion
      include: (str: string): void => {
        const haystack = typeof value === 'string' ? value : JSON.stringify(value);
        assert(haystack.includes(String(str)), `${JSON.stringify(value)} to include '${str}'`);
      },
      not: {
        be: buildBe(true),
        include: (str: string): void => {
          const haystack = typeof value === 'string' ? value : JSON.stringify(value);
          assert(!haystack.includes(String(str)), `${JSON.stringify(value)} to not include '${str}'`);
        },
      },
    },
  };
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 3 – SCRIPTED RUNNER: pm / postman SANDBOX
// ═══════════════════════════════════════════════════════════════════

interface SendRequestEntry {
  options: unknown;
  callback: (...args: unknown[]) => void;
}

interface Sandbox {
  pm: Record<string, unknown>;
  postman: Record<string, unknown>;
  getNextRequest: () => string | null | undefined;
  resetNextRequest: () => void;
  setResponse: (code: number, body: unknown) => void;
  flushPendingSendRequests: () => SendRequestEntry[];
}

/**
 * Create the pm and postman objects injected into every script.
 *
 * All scripts in a collection share the same envVars / collVars stores.
 * Each script runs in its own isolated VM context so var declarations
 * never leak between steps.
 */
function createSandbox(
  envVars: Record<string, string>,
  collVars: Record<string, string>,
): Sandbox {
  // undefined = not set (sequential), null = stop, string = jump to name
  let nextRequest: string | null | undefined = undefined;
  const pending: SendRequestEntry[] = [];

  let responseObj: Record<string, unknown> = {
    code: 0,
    text: (): string => '',
    json: (): null => null,
  };

  const pm: Record<string, unknown> = {
    environment: {
      set: (key: string, value: unknown): void => {
        envVars[key] = (value === null || value === undefined) ? '' : String(value);
      },
      get: (key: string): string => envVars[key] ?? '',
    },
    // pm.variables — Postman's unified variable accessor.
    // Writes go into envVars so {{token}} substitution (which checks envVars
    // before collVars in allVars()) picks them up. Reads check envVars first,
    // then fall through to collVars (matches Postman scope precedence:
    // local → environment → collection).
    // Without this, any collection that uses pm.variables.set/get fails silently.
    variables: {
      set: (key: string, value: unknown): void => {
        if (value === null || value === undefined) {
          envVars[key] = '';
        } else if (typeof value === 'object') {
          envVars[key] = JSON.stringify(value);
        } else {
          envVars[key] = String(value);
        }
      },
      get: (key: string): string => envVars[key] ?? collVars[key] ?? '',
    },
    collectionVariables: {
      get: (key: string): string => collVars[key] ?? '',
      set: (key: string, value: unknown): void => {
        collVars[key] = String(value ?? '');
      },
    },
    test: (name: string, fn: () => void): void => {
      try {
        fn();
        console.log(`     ✓ ${name}`);
      } catch (e: unknown) {
        console.warn(`     ✗ ${name}: ${e instanceof Error ? e.message : String(e)}`);
      }
    },
    expect: createExpect,
    get response(): Record<string, unknown> { return responseObj; },
    sendRequest: (
      options: unknown,
      callback: (...args: unknown[]) => void,
    ): void => {
      pending.push({ options, callback });
    },
    // pm.execution.setNextRequest — used by HOL collection for epoch looping
    execution: {
      setNextRequest: (name: string | null): void => {
        nextRequest = name;
      },
    },
  };

  const postman: Record<string, unknown> = {
    setNextRequest: (name: string | null): void => {
      nextRequest = name;
    },
  };

  return {
    pm,
    postman,
    getNextRequest: (): string | null | undefined => nextRequest,
    resetNextRequest: (): void => { nextRequest = undefined; },
    setResponse: (code: number, body: unknown): void => {
      const textFn = (): string =>
        typeof body === 'string' ? body : JSON.stringify(body ?? '');
      responseObj = {
        code,
        json: (): unknown => body,
        text: textFn,
        // pm.response.to.have.status(n) and pm.response.to.include(str)
        // used by ALL stablecoin-1 test scripts. Logs warnings, never throws.
        to: {
          have: {
            status: (expected: number): void => {
              if (code !== expected) {
                console.warn(`     ✗ pm.response.to.have.status(${expected}) — got ${code}`);
              }
            },
          },
          include: (str: string): void => {
            if (!textFn().includes(str)) {
              console.warn(`     ✗ pm.response.to.include('${str}') — not found in response`);
            }
          },
        },
      };
    },
    flushPendingSendRequests: (): SendRequestEntry[] => {
      const out = [...pending];
      pending.length = 0;
      return out;
    },
  };
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 4 – SCRIPTED RUNNER: SCRIPT EXECUTION + sendRequest
// ═══════════════════════════════════════════════════════════════════

/**
 * Run a script string inside an isolated VM context.
 *
 * pm, postman, and console are injected as globals.
 * All standard ECMAScript built-ins (String, Array, Math, Date, JSON, etc.)
 * are available automatically via runInNewContext.
 *
 * Errors are logged but never re-thrown — matches Postman behaviour where
 * a failing test script does not abort the collection.
 */
function runScript(
  code: string,
  pm: Record<string, unknown>,
  postman: Record<string, unknown>,
  label: string,
): void {
  if (!code.trim()) return;
  try {
    runInNewContext(
      code,
      { pm, postman, console },
      { filename: label, timeout: 60_000 },
    );
  } catch (e: unknown) {
    console.error(
      `     ⚠️  Script error [${label}]: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
}

/**
 * Execute a single pm.sendRequest() call and invoke its callback.
 *
 * Options: { url, method, header?, body?: { mode: 'raw', raw: string } }
 * All HTTP statuses are accepted — scripts check pm.response.code themselves.
 * Network failures invoke callback(err, null) so scripts can fallback to
 * their built-in JS models (as Approach3 does when ACTUS is unreachable).
 */
async function executeSendRequest(
  options: unknown,
  vars: Record<string, string>,
  callback: (...args: unknown[]) => void,
): Promise<void> {
  const opts = options as Record<string, any>;
  const rawUrl = typeof opts === 'string' ? opts : (opts?.url ?? '');
  const url = substituteVars(String(rawUrl), vars);
  const method = String(opts?.method ?? 'POST').toLowerCase();

  let data: unknown;
  if (opts?.body?.mode === 'raw' && opts?.body?.raw) {
    try { data = JSON.parse(String(opts.body.raw)); }
    catch { data = opts.body.raw; }
  }

  try {
    const res = await axios({
      method,
      url,
      data,
      headers: { 'Content-Type': 'application/json' },
      timeout: 15_000,
      validateStatus: () => true,
    });
    callback(null, {
      code: res.status,
      status: res.status,
      text: (): string =>
        typeof res.data === 'string' ? res.data : JSON.stringify(res.data),
      json: (): unknown => res.data,
    });
  } catch (err: unknown) {
    callback(err, null);
  }
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 5 – SCRIPTED RUNNER: FOLDER FLATTENING
// ═══════════════════════════════════════════════════════════════════

/**
 * Recursively flatten Postman folder items into a single ordered list.
 * A folder is any item that has a nested `item` array instead of a `request`.
 */
function flattenItems(items: any[]): any[] {
  const result: any[] = [];
  for (const item of items) {
    if (item.item && Array.isArray(item.item)) {
      result.push(...flattenItems(item.item));
    } else {
      result.push(item);
    }
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 6 – SCRIPTED RUNNER: MAIN FUNCTION
// ═══════════════════════════════════════════════════════════════════

async function runScriptedCollection(
  collectionJson: any,
  env: EnvironmentConfig,
  envName: string,
): Promise<StimulationResult> {
  const startTime = Date.now();
  const info = collectionJson.info || {};
  const steps: StepResult[] = [];

  // ── Variable stores ────────────────────────────────────────────
  // collVars: populated from the collection's top-level "variable" array
  const collVars: Record<string, string> = {};
  for (const v of (collectionJson.variable ?? []) as Array<{ key: string; value: unknown }>) {
    collVars[String(v.key)] = String(v.value ?? '');
  }

  // Override actus_sim_host with the chosen environment's host:port.
  // This is the single variable that controls which server all scripts hit.
  collVars['actus_sim_host'] = env.actusServerBase.replace(/^https?:\/\//, '');
  collVars['actus_risk_host'] = env.riskServiceBase.replace(/^https?:\/\//, '');

  // envVars: mutable state shared across all scripts via pm.environment
  const envVars: Record<string, string> = {};

  // allVars(): merged snapshot for URL substitution (envVars override collVars)
  const allVars = (): Record<string, string> => ({ ...collVars, ...envVars });

  // ── Build sandbox ──────────────────────────────────────────────
  const sandbox = createSandbox(envVars, collVars);
  // directSimulation: captures the response from a POST to the ACTUS server (port 8083).
  // stablecoin-1 collections use this path (not epoch_history) to return simulation data.
  let directSimulation: unknown = null;

  // Track the peak rt_history value — HOL collection's final summary resets it to '[]',
  // so we capture the longest version seen during execution.
  let peakCollHistory = '';

  // ── Flatten items and build name → index lookup ────────────────
  const flatItems = flattenItems(collectionJson.item || []);
  const nameToIndex: Record<string, number> = {};
  flatItems.forEach((item: any, i: number) => {
    if (item.name) nameToIndex[String(item.name)] = i;
  });

  console.log(`\n🚀 SimulationRunner [SCRIPTED]: ${info.name || 'Unknown'}`);
  console.log(`   Environment : ${envName}`);
  console.log(`   ACTUS server: ${env.actusServerBase}`);
  console.log(`   Flat items  : ${flatItems.length} (from ${(collectionJson.item || []).length} top-level)`);
  console.log('─'.repeat(60));

  // ── Collection-level prerequest scripts ──────────────────────
  // The top-level `event` array holds scripts that Postman runs ONCE before
  // any item. Used for derived variables shared across all requests (e.g. the
  // GTAP-grounded SOFR path in SWAPS-1LOAN-WHAT-IF-DEMO.json).
  // Without this block the per-item prerequests find no SOFR_PATH, no
  // swap_now_fixed_rate, etc., and the item bodies fail to materialise.
  const collEvents: any[] = Array.isArray(collectionJson.event) ? collectionJson.event : [];
  for (const ev of collEvents) {
    if (ev?.listen === 'prerequest') {
      const collExec = ev.script?.exec;
      const collCode = Array.isArray(collExec) ? collExec.join('\n') : String(collExec || '');
      if (collCode.trim()) {
        console.log(`   🔧 Running collection-level prerequest script...`);
        runScript(collCode, sandbox.pm, sandbox.postman, 'collection:prerequest');
        for (const { options, callback } of sandbox.flushPendingSendRequests()) {
          await executeSendRequest(options, allVars(), callback);
        }
      }
    }
  }

  // ── Execution loop ─────────────────────────────────────────────
  // MAX_ITERATIONS is a hard safety cap. Approach3 stops itself via
  // postman.setNextRequest at MAX_EPOCHS=60, so 200 is never reached
  // in normal operation.
  const MAX_ITERATIONS = 200;
  let currentIndex = 0;
  let iteration = 0;

  while (currentIndex < flatItems.length && iteration < MAX_ITERATIONS) {
    iteration++;
    const item = flatItems[currentIndex] as any;
    const itemName: string = String(item.name || `Item ${currentIndex}`);
    const stepStart = Date.now();

    // Must reset before each item so a previous setNextRequest cannot bleed
    sandbox.resetNextRequest();

    // ── Extract script blocks ──────────────────────────────────
    const events: any[] = Array.isArray(item.event) ? item.event : [];
    const prereqExec = events.find((e: any) => e.listen === 'prerequest')?.script?.exec;
    const testExec = events.find((e: any) => e.listen === 'test')?.script?.exec;
    const prereqCode = Array.isArray(prereqExec) ? prereqExec.join('\n') : String(prereqExec || '');
    const testCode = Array.isArray(testExec) ? testExec.join('\n') : String(testExec || '');

    // ── Step 1: prerequest script ──────────────────────────────
    if (prereqCode) {
      runScript(prereqCode, sandbox.pm, sandbox.postman, `${itemName}:prerequest`);
      // Flush pm.sendRequest() calls queued by the script (e.g. ACTUS /eventsBatch)
      for (const { options, callback } of sandbox.flushPendingSendRequests()) {
        await executeSendRequest(options, allVars(), callback);
      }
    }

    // ── Step 2: HTTP request ───────────────────────────────────
    // For Approach3 these are all GET {{actus_sim_host}}/ — dummy triggers.
    // ACTUS returns 404 for GET / and the test scripts explicitly accept
    // [200, 404, 405], so a non-200 here is normal and not treated as failure.
    let httpStatus = 0;
    let httpError: string | undefined;

    if (item.request) {
      const rawUrl: string =
        typeof item.request.url === 'string'
          ? item.request.url
          : String(item.request.url?.raw || '');
      const resolvedUrl = substituteVars(rawUrl, allVars());
      const method = String(item.request.method || 'GET').toLowerCase();

      // Extract and substitute request body (stablecoin-1 collections send real JSON payloads)
      let requestBody: unknown = undefined;
      if (item.request.body && item.request.body.raw) {
        const rawBody = substituteVars(String(item.request.body.raw), allVars());
        try {
          requestBody = JSON.parse(rawBody);
        } catch {
          requestBody = rawBody;
        }
      }

      console.log(`   [${String(iteration).padStart(3)}] ${itemName}`);
      console.log(`          → ${method.toUpperCase()} ${resolvedUrl}`);

      try {
        const res = await axios({
          method,
          url: resolvedUrl,
          data: requestBody,
          headers: { 'Content-Type': 'application/json' },
          timeout: 30_000,
          validateStatus: () => true,
        });
        httpStatus = res.status;
        sandbox.setResponse(res.status, res.data);
        console.log(`          → HTTP ${res.status}`);
              // Capture POST to ACTUS server as the direct simulation result.
              // Recognise either the env base URL OR a URL with the SAME PORT as
              // ACTUS — the collection JSON hardcodes 127.0.0.1:8083 which does
              // NOT string-match localhost:8083 even though it's the same server.
              if (method === 'post' && res.status === 200) {
                let portMatches = false;
                try {
                  portMatches = new URL(resolvedUrl).port === new URL(env.actusServerBase).port;
                } catch { /* ignore parse error */ }
                if (portMatches || resolvedUrl.startsWith(env.actusServerBase)) {
                  directSimulation = res.data;
                }
              }
      } catch (err: unknown) {
        httpError = err instanceof Error ? err.message : String(err);
        sandbox.setResponse(0, null);
        console.warn(`          → Connection error: ${httpError}`);
      }
    } else {
      console.log(`   [${String(iteration).padStart(3)}] ${itemName} (script-only, no HTTP)`);
    }

    // ── Step 3: test script ────────────────────────────────────
    if (testCode) {
      runScript(testCode, sandbox.pm, sandbox.postman, `${itemName}:test`);
    }

    // ── Record step ────────────────────────────────────────────
    const resolvedUrl = substituteVars(
      typeof item.request?.url === 'string'
        ? String(item.request.url)
        : String(item.request?.url?.raw || ''),
      allVars(),
    );

    steps.push({
      step: iteration,
      name: itemName,
      method: String(item.request?.method || 'SCRIPT'),
      url: resolvedUrl,
      // 404 is expected for dummy GETs — only a hard connection failure counts
      status: (httpError && httpStatus === 0) ? 'failed' : 'success',
      httpStatus: httpStatus > 0 ? httpStatus : undefined,
      error: httpError,
      durationMs: Date.now() - stepStart,
    });

    // ── Capture peak rt_history before scripts can reset it ───
    const currentHistory = collVars['rt_history'] || '';
    if (currentHistory.length > peakCollHistory.length) {
      peakCollHistory = currentHistory;
    }

    // ── Routing via postman.setNextRequest() ───────────────────
    const nextReq = sandbox.getNextRequest();

    if (nextReq === null) {
      console.log(`   ⏹  Stopped by setNextRequest(null)`);
      break;
    } else if (typeof nextReq === 'string') {
      const targetIndex = nameToIndex[nextReq];
      if (targetIndex === undefined) {
        console.warn(`   ⚠️  setNextRequest('${nextReq}') — name not found, stopping`);
        break;
      }
      currentIndex = targetIndex;
    } else {
      // undefined → advance sequentially
      currentIndex++;
    }
  }

  if (iteration >= MAX_ITERATIONS) {
    console.warn(`   ⚠️  Safety cap reached: ${MAX_ITERATIONS} iterations`);
  }

  // ── Extract epoch_history as the simulation result ─────────────
  let epochHistory: unknown[] = [];
  try {
    const raw = envVars['epoch_history'] || peakCollHistory || '[]';
    const parsed: unknown = JSON.parse(raw);
    epochHistory = Array.isArray(parsed) ? parsed : [];
  } catch {
    epochHistory = [];
  }

  // Prefer epoch_history (Approach3 loop collections) over direct response.
  // stablecoin-1 collections produce directSimulation; Approach3 produces epochHistory.
  const simulationData: unknown = epochHistory.length > 0 ? epochHistory : directSimulation;
  const allStepsOk = steps.every(s => s.status === 'success');

  const description: string =
    typeof info.description === 'string'
      ? info.description
      : String((info.description as any)?.content ?? '');

  const totalDurationMs = Date.now() - startTime;
  console.log('─'.repeat(60));
  console.log(
    `   Total: ${totalDurationMs}ms | Iterations: ${iteration} | Epochs recorded: ${epochHistory.length}`,
  );
  console.log('');

  // Extract risk factor input time-series from collection
  const riskFactorData = extractRiskFactorInputs(collectionJson);

  return {
    success: allStepsOk && simulationData !== null,
    scenarioName: String(info.name || 'Unknown'),
    description,
    environment: envName,
    riskServiceUrl: env.riskServiceBase,
    actusServerUrl: env.actusServerBase,
    steps,
    simulation: simulationData,
    riskFactorData: Object.keys(riskFactorData).length > 0 ? riskFactorData : null,
    // Expose final envVars so the caller can read pm.environment.set() values
    // such as A_total / B_total / C_total written by test scripts.
    environmentVariables: { ...envVars },
    totalDurationMs,
    timestamp: new Date().toISOString(),
  };
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 7 – SIMPLE RUNNER (original logic, unchanged)
// ═══════════════════════════════════════════════════════════════════

async function runSimpleCollection(
  collectionJson: any,
  env: EnvironmentConfig,
  envName: string,
): Promise<StimulationResult> {
  const startTime = Date.now();
  const items: any[] = collectionJson.item || [];
  const info = collectionJson.info || {};
  const steps: StepResult[] = [];
  let simulation: any = null;
  let allSuccess = true;

  console.log(`\n🚀 SimulationRunner [SIMPLE]: ${info.name || 'Unknown'}`);
  console.log(`   Environment: ${envName}`);
  console.log(`   Risk Service: ${env.riskServiceBase}`);
  console.log(`   ACTUS Server: ${env.actusServerBase}`);
  console.log(`   Steps: ${items.length}`);
  console.log('─'.repeat(60));

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const request = item.request;
    if (!request) {
      console.warn(`   ⚠️  Step ${i + 1}: no request object, skipping`);
      continue;
    }

    const method: string = (request.method || 'GET').toUpperCase();
    const { port, path } = extractPathFromPostmanUrl(request.url);
    const baseUrl = resolveBaseUrl(port, env);
    const fullUrl = `${baseUrl}${path}`;

    let body: unknown = undefined;
    if (request.body && request.body.raw) {
      try { body = JSON.parse(request.body.raw); }
      catch { body = request.body.raw; }
    }

    const stepStart = Date.now();
    console.log(`   Step ${i + 1}/${items.length}: ${method} ${fullUrl}`);

    try {
      const response = await axios({
        method: method.toLowerCase() as string,
        url: fullUrl,
        data: body,
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000,
      });

      const stepResult: StepResult = {
        step: i + 1,
        name: item.name || `Step ${i + 1}`,
        method,
        url: fullUrl,
        status: 'success',
        httpStatus: response.status,
        response: response.data,
        durationMs: Date.now() - stepStart,
      };

      steps.push(stepResult);
      console.log(`   ✅ ${response.status} (${stepResult.durationMs}ms)`);

      if (port === '8083' && method === 'POST') {
        simulation = response.data;
      }
    } catch (error: unknown) {
      allSuccess = false;
      const err = error as any;
      const stepResult: StepResult = {
        step: i + 1,
        name: item.name || `Step ${i + 1}`,
        method,
        url: fullUrl,
        status: 'failed',
        httpStatus: err.response?.status,
        error: err.message,
        durationMs: Date.now() - stepStart,
      };

      steps.push(stepResult);
      console.error(`   ❌ FAILED: ${err.message}`);

      if (port === '8082') {
        console.error(`   🛑 Risk service step failed. Aborting remaining steps.`);
        break;
      }
    }
  }

  const totalDurationMs = Date.now() - startTime;
  console.log('─'.repeat(60));
  console.log(
    `   Total: ${totalDurationMs}ms | Steps: ${steps.length}/${items.length} | Success: ${allSuccess}`,
  );
  if (simulation) {
    const eventCount = (simulation?.[0]?.events?.length) ?? 0;
    console.log(`   Simulation events: ${eventCount}`);
  }
  console.log('');

  // Extract risk factor input time-series from collection
  const riskFactorData = extractRiskFactorInputs(collectionJson);

  return {
    success: allSuccess && simulation !== null,
    scenarioName: info.name || 'Unknown',
    description: info.description || '',
    environment: envName,
    riskServiceUrl: env.riskServiceBase,
    actusServerUrl: env.actusServerBase,
    steps,
    simulation,
    riskFactorData: Object.keys(riskFactorData).length > 0 ? riskFactorData : null,
    totalDurationMs,
    timestamp: new Date().toISOString(),
  };
}

// ═══════════════════════════════════════════════════════════════════
// SECTION 8 – PUBLIC ENTRY POINT (signature unchanged)
// ═══════════════════════════════════════════════════════════════════

/**
 * Execute all steps from a parsed Postman collection JSON.
 *
 * Automatically selects SCRIPTED or SIMPLE mode based on collection structure.
 * The returned StimulationResult shape is identical regardless of mode.
 *
 * @param collectionJson - The full parsed JSON of a Postman collection
 * @param env            - The environment config to use
 * @param envName        - Human-readable environment name for logging
 */
export async function runStimulation(
  collectionJson: any,
  env: EnvironmentConfig,
  envName: string,
): Promise<StimulationResult> {
  if (isScriptedCollection(collectionJson)) {
    console.log(`   🔬 Mode: SCRIPTED (pm.* sandbox + setNextRequest loop)`);
    return runScriptedCollection(collectionJson, env, envName);
  }
  console.log(`   ⚡ Mode: SIMPLE (plain HTTP chain)`);
  return runSimpleCollection(collectionJson, env, envName);
}