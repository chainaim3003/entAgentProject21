/**
 * ====================================================================
 * ACTUS Data Processor - Modular Post-Processing Logic
 * ====================================================================
 * Extracts and modularizes the post-processing logic from working tests
 * Converts raw ACTUS API responses into period-based formatted data
 * Used by both old and new verification tests for consistency
 * ====================================================================
 */

// =================================== Core Response Debugging ===================================

/**
 * Print the core ACTUS response for debugging
 * This shows exactly what the ACTUS API is returning
 */
export function printCoreACTUSResponse(rawResponse: any, apiUrl: string): void {
    console.error('\n=== CORE ACTUS API RESPONSE DEBUG ===');
    console.error(`API URL: ${apiUrl}`);
    console.error(`Response Status: ${rawResponse.status || 'Unknown'}`);
    console.error(`Response Headers: ${JSON.stringify(rawResponse.headers || {}, null, 2)}`);
    
    const data = rawResponse.data || rawResponse;
    console.error('\n--- Raw Response Data Structure ---');
    console.error(`Type: ${typeof data}`);
    console.error(`Keys: ${Object.keys(data || {})}`);
    
    if (data) {
        console.error('\n--- Raw Data Sample ---');
        console.error(JSON.stringify(data, null, 2));
        
        // Specific checks for common ACTUS response patterns
        if (data.inflow) console.error(`Inflow periods: ${Array.isArray(data.inflow) ? data.inflow.length : 'Not array'}`);
        if (data.outflow) console.error(`Outflow periods: ${Array.isArray(data.outflow) ? data.outflow.length : 'Not array'}`);
        if (data.monthsCount !== undefined) console.error(`Months count: ${data.monthsCount}`);
        if (data.periodsCount !== undefined) console.error(`Periods count: ${data.periodsCount}`);
        if (data.contractDetails) console.error(`Contract details: ${Array.isArray(data.contractDetails) ? data.contractDetails.length : 'Not array'} contracts`);
    }
    
    console.error('=== END CORE ACTUS RESPONSE DEBUG ===\n');
}

// =================================== Post-Processing Logic ===================================

/**
 * Interface for processed ACTUS event data (from working test)
 */
interface ACTUSEvent {
    time: string;
    payoff: number;
}

interface ACTUSContract {
    id: string;
    contractId: string;
    type: string;
    events: ACTUSEvent[];
}

/**
 * Process raw ACTUS JSON data using the EXACT logic from working test
 * This preserves the period calculation and [0]-init + .push() array pattern
 */
export function processRawACTUSData(rawData: any): {
    inflow: number[][];
    outflow: number[][];
    monthsCount: number;
    contractDetails: any[];
} {
    console.error('\n=== PROCESSING RAW ACTUS DATA ===');
    console.error('Raw data type:', typeof rawData);
    
    // Parse the data if it's a string, or use directly if it's already an array
    let parsedData: ACTUSContract[];
    if (typeof rawData === 'string') {
        parsedData = JSON.parse(rawData);
    } else if (Array.isArray(rawData)) {
        parsedData = rawData;
    } else {
        throw new Error('Invalid ACTUS data format - expected string or array');
    }
    
    console.error(`Parsed ${parsedData.length} contracts`);
    parsedData.forEach((contract, i) => {
        console.error(`Contract ${i}: ${contract.contractId} (${contract.type || 'unknown'}) with ${contract.events?.length || 0} events`);
    });
    
    // Extract all dates to calculate the date range (EXACT logic from working test)
    const allDates = parsedData.flatMap(contract => 
        contract.events?.map(event => new Date(event.time)) || []
    );
    
    if (allDates.length === 0) {
        console.error('⚠️ No events found in contracts');
        return {
            inflow: [],
            outflow: [],
            monthsCount: 0,
            contractDetails: []
        };
    }
    
    const minDate = new Date(Math.min(...allDates.map(date => date.getTime())));
    const maxDate = new Date(Math.max(...allDates.map(date => date.getTime())));
    
    // Calculate months count (EXACT logic from working test)
    const monthsCount = Math.max(
        (maxDate.getFullYear() - minDate.getFullYear()) * 12 + (maxDate.getMonth() - minDate.getMonth()) + 1,
        1
    );
    
    console.error(`Date range: ${minDate.toISOString()} to ${maxDate.toISOString()}`);
    console.error(`Calculated ${monthsCount} periods`);
    
    // Initialize arrays (EXACT logic from working test - [0] init + .push())
    const inflow: number[][] = Array.from({ length: monthsCount }, () => [0]);
    const outflow: number[][] = Array.from({ length: monthsCount }, () => [0]);
    
    // Process events into inflow/outflow arrays (EXACT logic from working test)
    parsedData.forEach((contract: ACTUSContract) => {
        contract.events?.forEach((event: ACTUSEvent) => {
            const date = new Date(event.time);
            const monthIndex = (date.getFullYear() - minDate.getFullYear()) * 12 + (date.getMonth() - minDate.getMonth());
            
            if (monthIndex >= 0 && monthIndex < monthsCount) {
                if (event.payoff > 0) {
                    inflow[monthIndex].push(event.payoff);
                } else if (event.payoff < 0) {
                    outflow[monthIndex].push(Math.abs(event.payoff));
                }
            }
        });
    });
    
    // Build contract detail summary
    const contractDetails = parsedData.map((c, i) => ({
        contractId: c.contractId,
        contractIndex: i,
        eventCount: (c.events || []).length,
        totalPayoff: (c.events || []).reduce((sum, e) => sum + e.payoff, 0)
    }));
    
    console.error('Post-processing complete:');
    console.error(`- Inflow periods: ${inflow.length}`);
    console.error(`- Outflow periods: ${outflow.length}`);
    
    // Debug: show sample data
    console.error('- Sample inflow data:');
    inflow.slice(0, 3).forEach((period, i) => {
        const total = period.reduce((sum, val) => sum + val, 0);
        console.error(`  Period ${i}: ${period.length} events, total: ${total}`);
    });
    
    console.error('=== END PROCESSING RAW ACTUS DATA ===\n');
    
    return { inflow, outflow, monthsCount, contractDetails };
}