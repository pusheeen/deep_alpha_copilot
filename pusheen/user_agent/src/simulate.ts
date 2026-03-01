#!/usr/bin/env node
/**
 * Generalized User Agent Simulator
 *
 * Usage:
 *   npx tsx src/simulate.ts --config configs/closed-loop.json
 *   npx tsx src/simulate.ts --url https://example.com --spec "A landing page for..."
 *   npx tsx src/simulate.ts --config configs/closed-loop.json --no-browser
 *   npx tsx src/simulate.ts --config configs/closed-loop.json --browser-only
 *
 * The simulator runs 4 phases:
 * 1. HTTP-level user flows (register, login, API calls)
 * 2. Static HTML audits (cheerio-based structure/accessibility checks)
 * 3. Browser testing with Playwright (real rendering, form filling, screenshots)
 * 4. Scoring & report generation
 */
import fs from 'fs';
import path from 'path';
import { FlowRunner } from './flow-runner.js';
import { auditPage } from './auditor.js';
import { BrowserRunner } from './browser-runner.js';
import { generateReport } from './scorer.js';
import type { SiteConfig, BrowserPageResult, BrowserFlowResult } from './types.js';

async function main() {
  const args = process.argv.slice(2);
  let config: SiteConfig;

  const noBrowser = args.includes('--no-browser');
  const browserOnly = args.includes('--browser-only');

  // Parse args
  const configIdx = args.indexOf('--config');
  const urlIdx = args.indexOf('--url');
  const specIdx = args.indexOf('--spec');

  if (configIdx !== -1 && args[configIdx + 1]) {
    const configPath = path.resolve(args[configIdx + 1]);
    config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  } else if (urlIdx !== -1 && args[urlIdx + 1]) {
    config = {
      site_name: new URL(args[urlIdx + 1]).hostname,
      base_url: args[urlIdx + 1].replace(/\/$/, ''),
      spec: specIdx !== -1 ? args[specIdx + 1] || '' : '',
      flows: [],
      pages_to_audit: ['/'],
      evaluation_criteria: ['usability', 'visual_design', 'performance', 'accessibility'],
    };
  } else {
    // Default: closed-loop config
    const defaultConfig = path.join(import.meta.dirname || __dirname, '..', 'configs', 'closed-loop.json');
    if (fs.existsSync(defaultConfig)) {
      config = JSON.parse(fs.readFileSync(defaultConfig, 'utf-8'));
    } else {
      console.error('Usage: npx tsx src/simulate.ts --config <path> | --url <url> [--spec "<spec>"]');
      process.exit(1);
    }
  }

  console.log('='.repeat(70));
  console.log(`  User Agent Simulator — ${config.site_name}`);
  console.log(`  Target: ${config.base_url}`);
  console.log(`  Mode: ${browserOnly ? 'browser-only' : noBrowser ? 'http-only' : 'full (http + browser)'}`);
  console.log('='.repeat(70));

  // ── Phase 1: HTTP-level Flows ───────────────────────────────────────
  const runner = new FlowRunner(config.base_url);
  if (!browserOnly) {
    console.log('\n[Phase 1] Running HTTP-level user flows...');
    for (const flow of config.flows) {
      await runner.runFlow(flow);
    }
  }

  // ── Phase 2: Static HTML Audits ─────────────────────────────────────
  const audits = [];
  if (!browserOnly) {
    console.log('\n[Phase 2] Auditing pages (static HTML)...');
    for (const pagePath of config.pages_to_audit) {
      console.log(`  Auditing ${pagePath}...`);
      const audit = await auditPage(config.base_url, pagePath);
      audits.push(audit);
      console.log(
        `    Status: ${audit.status}, ${audit.timing_ms}ms, ${Math.round(audit.html_size_bytes / 1024)}KB`
      );
    }
  }

  // ── Phase 3: Browser Testing (Playwright) ───────────────────────────
  let browserPageResults: BrowserPageResult[] = [];
  let browserFlowResults: BrowserFlowResult[] = [];

  if (!noBrowser) {
    console.log('\n[Phase 3] Browser testing with Playwright...');

    const reportsDir = path.join(import.meta.dirname || __dirname, '..', 'reports');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const screenshotDir = path.join(reportsDir, `screenshots-${timestamp}`);

    const browser = new BrowserRunner(config.base_url, screenshotDir);

    try {
      await browser.launch();
      console.log('  Browser launched (Chromium headless)');

      // 3a: Render each page in a real browser and analyze
      console.log('\n  [3a] Rendering pages in browser...');
      for (const pagePath of config.pages_to_audit) {
        console.log(`    Rendering ${pagePath}...`);
        const result = await browser.auditPage(pagePath);
        browserPageResults.push(result);

        const issues: string[] = [];
        if (result.console_errors.length > 0) issues.push(`${result.console_errors.length} console errors`);
        if (result.network_errors.length > 0) issues.push(`${result.network_errors.length} network errors`);
        if (result.has_raw_html_leak) issues.push('RAW HTML LEAK DETECTED');
        if (result.broken_images.length > 0) issues.push(`${result.broken_images.length} broken images`);
        if (!result.has_visible_content) issues.push('NO VISIBLE CONTENT');

        const status = issues.length > 0 ? issues.join(', ') : 'OK';
        console.log(`      ${result.load_time_ms}ms, ${Math.round(result.rendered_html_size / 1024)}KB rendered — ${status}`);
      }

      // 3b: Run browser-based user flows
      if (config.browser_flows && config.browser_flows.length > 0) {
        console.log('\n  [3b] Running browser user flows...');
        for (const flow of config.browser_flows) {
          console.log(`\n    Flow: ${flow.name}`);
          const result = await browser.runFlow(flow);
          browserFlowResults.push(result);

          const passCount = result.steps.filter((s) => s.success).length;
          const icon = result.success ? 'PASS' : 'FAIL';
          console.log(`    ${icon} ${flow.name}: ${passCount}/${result.steps.length} steps, ${result.duration_ms}ms`);
        }
      }

      console.log(`\n  Screenshots saved to: ${screenshotDir}`);
    } catch (e) {
      console.error(`  Browser testing failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      await browser.close();
    }
  }

  // ── Phase 4: Score & Report ─────────────────────────────────────────
  console.log('\n[Phase 4] Generating report...');

  const report = generateReport(
    config,
    runner.getResults(),
    audits,
    browserPageResults,
    browserFlowResults
  );

  // ── Save Report ─────────────────────────────────────────────────────
  const reportsDir = path.join(import.meta.dirname || __dirname, '..', 'reports');
  if (!fs.existsSync(reportsDir)) {
    fs.mkdirSync(reportsDir, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const safeName = config.site_name.toLowerCase().replace(/\s+/g, '-');
  const reportPath = path.join(reportsDir, `${safeName}-${timestamp}.md`);
  const jsonPath = path.join(reportsDir, `${safeName}-${timestamp}.json`);

  fs.writeFileSync(reportPath, report.detailed_feedback);
  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));

  // ── Print Summary ───────────────────────────────────────────────────
  console.log('\n' + '='.repeat(70));
  console.log(`  OVERALL SCORE: ${report.overall_score}/100`);
  console.log('='.repeat(70));

  if (report.critical_issues.length > 0) {
    console.log('\n  Critical Issues:');
    for (const issue of report.critical_issues) {
      console.log(`    - ${issue}`);
    }
  }

  if (report.positive_aspects.length > 0) {
    console.log('\n  What Works Well:');
    for (const p of report.positive_aspects) {
      console.log(`    + ${p}`);
    }
  }

  console.log(`\n  Report saved to:`);
  console.log(`    ${reportPath}`);
  console.log(`    ${jsonPath}`);

  return report;
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
