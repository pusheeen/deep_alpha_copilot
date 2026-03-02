/**
 * Flow runner — executes user flows (register, login, browse, etc.)
 * and records results for each step.
 */
import { timedFetch } from './fetcher.js';
import type { Flow, FlowStep, StepResult } from './types.js';

export class FlowRunner {
  private baseUrl: string;
  private token: string | null = null;
  private registeredEmail: string | null = null;
  private results: StepResult[] = [];
  private sessionTs: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.sessionTs = String(Date.now());
  }

  getResults(): StepResult[] {
    return this.results;
  }

  private interpolate(value: string): string {
    return value
      .replace(/\{timestamp\}/g, this.sessionTs)
      .replace(/\{registered_email\}/g, this.registeredEmail || '');
  }

  private interpolateBody(body: Record<string, unknown>): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(body)) {
      if (typeof v === 'string') {
        result[k] = this.interpolate(v);
      } else if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
        result[k] = this.interpolateBody(v as Record<string, unknown>);
      } else {
        result[k] = v;
      }
    }
    return result;
  }

  async runFlow(flow: Flow): Promise<void> {
    console.log(`\n  Flow: ${flow.name}`);
    for (const step of flow.steps) {
      await this.runStep(flow.name, step);
    }
  }

  private async runStep(flowName: string, step: FlowStep): Promise<void> {
    const url = `${this.baseUrl}${this.interpolate(step.url)}`;

    const headers: Record<string, string> = {};
    if (step.auth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (step.body) {
      headers['Content-Type'] = 'application/json';
    }

    const options: RequestInit = {
      method: step.method || 'GET',
      headers,
    };
    if (step.body) {
      options.body = JSON.stringify(this.interpolateBody(step.body));
    }

    const start = Date.now();
    const result = await timedFetch(url, options);

    const stepResult: StepResult = {
      flow: flowName,
      step: step.action,
      action: step.action,
      url: step.url,
      success: false,
      status: result.status,
      timing_ms: result.timing_ms,
      expected: step.expect,
      actual: '',
    };

    if (result.error) {
      stepResult.actual = `Error: ${result.error}`;
      stepResult.error = result.error;
    } else if (step.action === 'timing') {
      const threshold = parseInt(step.expect.replace(/[^0-9]/g, ''), 10);
      stepResult.success = result.timing_ms < threshold;
      stepResult.actual = `${result.timing_ms}ms (threshold: ${threshold}ms)`;
    } else if (step.action === 'fetch_page') {
      stepResult.success = result.ok;
      stepResult.actual = `Status ${result.status}, ${result.body.length} bytes, ${result.timing_ms}ms`;
    } else if (step.action === 'api_call') {
      stepResult.success = result.ok;
      const json = result.json as Record<string, unknown> | null;

      if (json?.error) {
        stepResult.actual = `Error: ${json.error}`;
        stepResult.success = false;
      } else if (json) {
        // Save token if needed
        if (step.save_token && json.access_token) {
          this.token = json.access_token as string;
          // Save email for login flow
          if (step.body?.email) {
            this.registeredEmail = this.interpolate(step.body.email as string);
          }
        }

        // Summarize response
        const keys = Object.keys(json);
        stepResult.actual = `OK — keys: [${keys.join(', ')}]`;
        stepResult.details = json;
        stepResult.success = true;
      } else {
        stepResult.actual = `Non-JSON response: ${result.body.slice(0, 200)}`;
      }
    }

    const icon = stepResult.success ? '  PASS' : '  FAIL';
    console.log(`    ${icon} [${step.action}] ${step.url} — ${stepResult.actual.slice(0, 100)}`);

    this.results.push(stepResult);
  }
}
