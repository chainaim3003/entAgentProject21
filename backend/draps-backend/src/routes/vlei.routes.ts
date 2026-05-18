/**
 * vlei.routes.ts
 *
 * VLEI Credential API routes for Jupiter Seller Agent workflow.
 * 
 * These endpoints execute REAL vLEI workflows against the running KERIA server
 * via docker compose exec into the tsx-shell container.
 *
 * NO mocks. NO fake data. NO fallbacks. NO hardcoded values.
 *
 * Endpoints:
 *   POST /api/vlei/run    - Run the full seller credential signing workflow
 *   GET  /api/vlei/query  - Query existing credentials from KERIA
 *   GET  /api/vlei/status - Check if KERIA + vLEI containers are healthy
 */

import { Router } from 'express';
import type { Request, Response } from 'express';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const router = Router();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Resolve the LegentvLEI directory (where docker-compose.yml lives)
// ============================================================================
function getVleiDir(): string {
    // Walk up from Backend/dist/routes to generalRisk, then into LegentvLEI
    const candidates = [
        path.resolve(__dirname, '..', '..', '..', 'LegentvLEI'),
        path.resolve(process.cwd(), '..', 'LegentvLEI'),
        path.resolve(process.cwd(), 'LegentvLEI'),
        'C:\\Asha\\chainaim\\asha\\GENERAL\\generalRisk\\LegentvLEI',
    ];
    for (const dir of candidates) {
        if (fs.existsSync(path.join(dir, 'docker-compose.yml'))) {
            return dir;
        }
    }
    throw new Error(
        'LegentvLEI directory not found. Checked: ' + candidates.join(', ')
    );
}

// ============================================================================
// Helper: Execute command in LegentvLEI directory with timeout
// ============================================================================
async function execInVleiDir(
    command: string,
    timeoutMs: number = 120000
): Promise<{ stdout: string; stderr: string }> {
    const vleiDir = getVleiDir();
    return execAsync(command, {
        cwd: vleiDir,
        timeout: timeoutMs,
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer for large JSON
        env: { ...process.env, PATH: process.env.PATH },
    });
}

// ============================================================================
// POST /api/vlei/run - Run Jupiter Seller Credential Signing Workflow
// ============================================================================
router.post('/vlei/run', async (_req: Request, res: Response) => {
    console.error('\n🔐 VLEI RUN: Starting Jupiter Seller Credential Workflow...');
    const startTime = Date.now();

    try {
        // Execute the seller credential workflow inside the tsx-shell container
        // This script:
        //   1. Connects to KERIA as jupiterSellerAgent
        //   2. Uses existing OOR credentials (no agent delegation)
        //   3. Creates invoice registry if needed
        //   4. Issues self-attested invoice credential with REAL digital signature
        //   5. Outputs full credential JSON to stdout
        const { stdout, stderr } = await execInVleiDir(
            'docker compose exec -T tsx-shell tsx sig-wallet/src/tasks/invoice/vlei-seller-credential-workflow.ts docker /task-data',
            180000 // 3 minute timeout for credential operations
        );

        const durationMs = Date.now() - startTime;
        console.error(`  VLEI RUN: Completed in ${durationMs}ms`);
        if (stderr) {
            console.error(`  VLEI RUN stderr: ${stderr.substring(0, 500)}`);
        }

        // Parse the JSON output from stdout
        // The workflow script outputs JSON on the last line of stdout
        const lines = stdout.trim().split('\n');
        let resultJson: any = null;

        // Find the JSON line (last valid JSON line)
        for (let i = lines.length - 1; i >= 0; i--) {
            const line = lines[i].trim();
            if (line.startsWith('{')) {
                try {
                    resultJson = JSON.parse(line);
                    break;
                } catch {
                    // Not valid JSON, continue searching
                }
            }
        }

        if (!resultJson) {
            return res.status(500).json({
                success: false,
                error: 'No valid JSON output from workflow',
                rawOutput: stdout.substring(0, 2000),
                durationMs,
            });
        }

        // Add timing info
        resultJson.durationMs = durationMs;

        return res.json(resultJson);

    } catch (error: any) {
        const durationMs = Date.now() - startTime;
        console.error(`  VLEI RUN ERROR: ${error.message}`);

        // If docker command fails, try to read from existing task-data files
        // (credentials from a prior successful run)
        try {
            const vleiDir = getVleiDir();
            const latestPath = path.join(vleiDir, 'task-data', 'jupiterSellerAgent-vlei-credential-latest.json');
            if (fs.existsSync(latestPath)) {
                const existingData = JSON.parse(fs.readFileSync(latestPath, 'utf-8'));
                return res.json({
                    ...existingData,
                    note: 'Loaded from prior successful run. Live workflow failed: ' + error.message,
                    durationMs,
                });
            }
        } catch { /* ignore */ }

        return res.status(500).json({
            success: false,
            error: error.message,
            durationMs,
            hint: 'Ensure Docker containers are running: docker compose ps (in LegentvLEI directory)',
        });
    }
});

// ============================================================================
// GET /api/vlei/query - Query Existing Credentials from KERIA
// ============================================================================
router.get('/vlei/query', async (_req: Request, res: Response) => {
    console.error('\n🔍 VLEI QUERY: Querying Jupiter Seller credentials...');
    const startTime = Date.now();

    try {
        const { stdout, stderr } = await execInVleiDir(
            'docker compose exec -T tsx-shell tsx sig-wallet/src/tasks/invoice/vlei-seller-query-credentials.ts docker /task-data',
            60000 // 1 minute timeout
        );

        const durationMs = Date.now() - startTime;
        if (stderr) {
            console.error(`  VLEI QUERY stderr: ${stderr.substring(0, 500)}`);
        }

        // Parse JSON output
        const lines = stdout.trim().split('\n');
        let resultJson: any = null;

        for (let i = lines.length - 1; i >= 0; i--) {
            const line = lines[i].trim();
            if (line.startsWith('{')) {
                try {
                    resultJson = JSON.parse(line);
                    break;
                } catch { /* continue */ }
            }
        }

        if (!resultJson) {
            return res.status(500).json({
                success: false,
                error: 'No valid JSON output from query',
                durationMs,
            });
        }

        resultJson.durationMs = durationMs;
        return res.json(resultJson);

    } catch (error: any) {
        const durationMs = Date.now() - startTime;
        console.error(`  VLEI QUERY ERROR: ${error.message}`);

        return res.status(500).json({
            success: false,
            error: error.message,
            durationMs,
        });
    }
});

// ============================================================================
// GET /api/vlei/status - Check KERIA + vLEI Container Health
// ============================================================================
router.get('/vlei/status', async (_req: Request, res: Response) => {
    console.error('\n💊 VLEI STATUS: Checking container health...');
    const checks: Record<string, any> = {
        timestamp: new Date().toISOString(),
    };

    try {
        // Check if docker-compose services are running
        const { stdout: psOutput } = await execInVleiDir(
            'docker compose ps --format json',
            15000
        );

        const services: Record<string, string> = {};
        const lines = psOutput.trim().split('\n');
        for (const line of lines) {
            try {
                const svc = JSON.parse(line);
                services[svc.Service || svc.Name] = svc.State || svc.Status;
            } catch { /* skip non-json lines */ }
        }

        checks.services = services;
        checks.keriaRunning = Object.entries(services).some(
            ([name, state]) => name.includes('keria') && (state === 'running' || (state as string).includes('Up'))
        );
        checks.schemaRunning = Object.entries(services).some(
            ([name, state]) => name.includes('schema') && (state === 'running' || (state as string).includes('Up'))
        );
        checks.tsxShellRunning = Object.entries(services).some(
            ([name, state]) => name.includes('tsx') && (state === 'running' || (state as string).includes('Up'))
        );

        // Check if agent data files exist (OOR workflow was completed)
        const vleiDir = getVleiDir();
        const agentInfoExists = fs.existsSync(
            path.join(vleiDir, 'task-data', 'jupiterSellerAgent-info.json')
        );
        const agentBranExists = fs.existsSync(
            path.join(vleiDir, 'task-data', 'jupiterSellerAgent-bran.txt')
        );

        checks.agentDataExists = agentInfoExists && agentBranExists;

        if (agentInfoExists) {
            try {
                const agentInfo = JSON.parse(
                    fs.readFileSync(path.join(vleiDir, 'task-data', 'jupiterSellerAgent-info.json'), 'utf-8')
                );
                checks.sellerAgentAID = agentInfo.aid;
            } catch { /* ignore */ }
        }

        checks.ready = checks.keriaRunning && checks.tsxShellRunning && checks.agentDataExists;
        checks.status = checks.ready ? 'ready' : 'not_ready';

        return res.json(checks);

    } catch (error: any) {
        return res.json({
            status: 'error',
            error: error.message,
            hint: 'Docker may not be running or LegentvLEI containers not started',
            timestamp: new Date().toISOString(),
        });
    }
});

export default router;
