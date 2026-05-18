/**
 * Monitoring Time Generator
 * Generates array of ISO timestamps based on start/end/frequency
 */

import { addDays, addWeeks, addMonths, format, parseISO } from 'date-fns';

export function generateMonitoringTimes(
  startDate: string,
  endDate: string,
  frequency: 'daily' | 'weekly' | 'monthly'
): string[] {
  const start = parseISO(startDate);
  const end = parseISO(endDate);
  const times: string[] = [];
  
  let current = start;
  
  while (current <= end) {
    times.push(format(current, "yyyy-MM-dd'T'HH:mm:ss"));
    
    switch (frequency) {
      case 'daily':
        current = addDays(current, 1);
        break;
      case 'weekly':
        current = addWeeks(current, 1);
        break;
      case 'monthly':
        current = addMonths(current, 1);
        break;
    }
  }
  
  return times;
}
