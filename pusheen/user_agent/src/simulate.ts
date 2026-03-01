#!/usr/bin/env node
/**
 * Generalized User Agent Simulator
 *
 * Usage:
 *   npx tsx src/simulate.ts --config configs/closed-loop.json
 *   npx tsx src/simulate.ts --url https://example.com --spec "A landing page for..."
 *
 * The simulator:
 * 1. Runs all user flows defined in the config
 * 2. Audits all pages for accessibility, structure, and performance
 * 3. Scores the site across multiple criteria
 * 4. Generates a detailed feedback report
 */
import fs from 'fs';
import path from 'path';
import { FlowRunner } from './flow-runner.js';
import { auditPage } from './auditor.js';
import { generateReport } from './scorer.js';
import type { SiteConfig, FeedbackReport } from './types.js';

async function main() {
  const args = process.argv.slice(2);
  let config: SiteConfig;

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
  console.log('='.repeat(70));

  // ── Phase 1: Run Flows ──────────────────────────────────────────────
  console.log('\n[Phase 1] Running user flows...');

  const runner = new FlowRunner(config.base_url);
  for (const flow of config.flows) {
    await runner.runFlow(flow);
  }

  // ── Phase 2: Audit Pages ────────────────────────────────────────────
  console.log('\n[Phase 2] Auditing pages...');

  const audits = [];
  for (const pagePath of config.pages_to_audit) {
    console.log(`  Auditing ${pagePath}...`);
    const audit = await auditPage(config.base_url, pagePath);
    audits.push(audit);
    console.log(
      `    Status: ${audit.status}, ${audit.timing_ms}ms, ${Math.round(audit.html_size_bytes / 1024)}KB`
    );
  }

  // ── Phase 3: Score & Report ─────────────────────────────────────────
  console.log('\n[Phase 3] Generating report...');

  const report = generateReport(config, runner.getResults(), audits);

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
