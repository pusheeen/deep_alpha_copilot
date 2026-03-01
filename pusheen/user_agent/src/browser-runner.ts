/**
 * Browser-based testing with Playwright.
 *
 * Unlike the HTTP-level flow-runner, this actually launches a real browser,
 * renders JavaScript, fills forms, clicks buttons, and sees what a real user sees.
 */
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright';
import fs from 'fs';
import path from 'path';
import type {
  BrowserFlow,
  BrowserStep,
  BrowserFlowResult,
  BrowserStepResult,
  BrowserPageResult,
} from './types.js';

export class BrowserRunner {
  private baseUrl: string;
  private screenshotDir: string;
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private sessionTs: string;

  constructor(baseUrl: string, screenshotDir: string) {
    this.baseUrl = baseUrl;
    this.screenshotDir = screenshotDir;
    this.sessionTs = String(Date.now());
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir, { recursive: true });
    }
  }

  async launch(): Promise<void> {
    this.browser = await chromium.launch({ headless: true });
    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 800 },
      userAgent: 'UserAgentSimulator/1.0 (Playwright)',
    });
  }

  async close(): Promise<void> {
    if (this.context) await this.context.close();
    if (this.browser) await this.browser.close();
    this.browser = null;
    this.context = null;
  }

  /**
   * Visit a page, wait for it to fully render (including client-side JS),
   * take a screenshot, and analyze what's actually visible.
   */
  async auditPage(pagePath: string): Promise<BrowserPageResult> {
    if (!this.context) throw new Error('Browser not launched. Call launch() first.');

    const page = await this.context.newPage();
    const url = `${this.baseUrl}${pagePath}`;
    const consoleErrors: string[] = [];
    const consoleWarnings: string[] = [];
    const networkErrors: string[] = [];

    // Capture console messages
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
      if (msg.type() === 'warning') consoleWarnings.push(msg.text());
    });

    // Capture failed network requests
    page.on('requestfailed', (req) => {
      networkErrors.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText || 'unknown'}`);
    });

    const start = Date.now();

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    } catch {
      // networkidle may time out on long-polling pages, fall back to load
      try {
        await page.goto(url, { waitUntil: 'load', timeout: 15000 });
      } catch {
        // page completely failed to load
      }
    }

    // Wait a bit for React hydration / client-side rendering
    await page.waitForTimeout(2000);

    const loadTime = Date.now() - start;

    // Screenshot
    const safeName = pagePath.replace(/\//g, '_').replace(/^_/, '') || 'index';
    const screenshotPath = path.join(this.screenshotDir, `${safeName}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });

    // Get visible text (what a user actually reads)
    const visibleText = await page.evaluate(() => {
      return document.body?.innerText || '';
    });

    // Get rendered HTML size
    const renderedHtml = await page.content();

    // Check for raw HTML leaking into visible content
    const rawHtmlCheck = await page.evaluate(() => {
      const body = document.body?.innerText || '';
      const patterns = [
        /&lt;/g, /&gt;/g, /&amp;(?!amp;)/g, /&quot;/g,
        /<[a-z][a-z0-9]*\s/gi,  // HTML tags in text
        /&nbsp;/g,
      ];
      const snippets: string[] = [];

      // Check all text nodes for HTML entities or tags
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const text = node.textContent || '';
        if (
          text.includes('&lt;') || text.includes('&gt;') || text.includes('&nbsp;') ||
          /<[a-z][a-z0-9]*[\s>]/i.test(text)
        ) {
          const snippet = text.trim().slice(0, 200);
          if (snippet.length > 5) snippets.push(snippet);
        }
      }
      return snippets;
    });

    // Check for broken images
    const brokenImages = await page.evaluate(() => {
      const imgs = Array.from(document.querySelectorAll('img'));
      return imgs
        .filter((img) => !img.complete || img.naturalWidth === 0)
        .map((img) => img.src || img.getAttribute('data-src') || 'unknown');
    });

    // Check for empty containers that should have content
    const emptyContainers = await page.evaluate(() => {
      const empties: string[] = [];
      const containers = document.querySelectorAll('main, section, article, [role="main"], .feed, .content');
      containers.forEach((el) => {
        const text = (el as HTMLElement).innerText?.trim();
        if (!text || text.length < 10) {
          const tag = el.tagName.toLowerCase();
          const cls = el.className ? `.${String(el.className).split(' ')[0]}` : '';
          empties.push(`<${tag}${cls}> is empty or near-empty`);
        }
      });
      return empties;
    });

    // Count interactive and clickable elements
    const { interactive, clickable } = await page.evaluate(() => {
      const interactiveEls = document.querySelectorAll(
        'a, button, input, select, textarea, [role="button"], [tabindex]'
      );
      const clickableEls = document.querySelectorAll('a[href], button, [role="button"], [onclick]');
      return { interactive: interactiveEls.length, clickable: clickableEls.length };
    });

    const hasVisibleContent = visibleText.trim().length > 50;

    await page.close();

    return {
      url,
      page_path: pagePath,
      screenshot_path: screenshotPath,
      load_time_ms: loadTime,
      console_errors: consoleErrors,
      console_warnings: consoleWarnings,
      network_errors: networkErrors,
      visible_text: visibleText.slice(0, 3000),
      rendered_html_size: renderedHtml.length,
      has_visible_content: hasVisibleContent,
      has_raw_html_leak: rawHtmlCheck.length > 0,
      raw_html_snippets: rawHtmlCheck,
      broken_images: brokenImages,
      overlapping_elements: [], // would need visual regression for this
      empty_containers: emptyContainers,
      interactive_elements_count: interactive,
      clickable_elements_count: clickable,
    };
  }

  /**
   * Run a browser-based user flow: actually click buttons, fill forms,
   * navigate pages — like a real user would.
   */
  async runFlow(flow: BrowserFlow): Promise<BrowserFlowResult> {
    if (!this.context) throw new Error('Browser not launched. Call launch() first.');

    const page = await this.context.newPage();
    const stepResults: BrowserStepResult[] = [];
    const screenshots: string[] = [];
    const flowStart = Date.now();
    let flowSuccess = true;

    for (let i = 0; i < flow.steps.length; i++) {
      const step = flow.steps[i];
      const stepStart = Date.now();
      let success = true;
      let error: string | undefined;
      let screenshotPath: string | undefined;

      try {
        await this.executeStep(page, step);
      } catch (e) {
        success = false;
        flowSuccess = false;
        error = e instanceof Error ? e.message : String(e);
      }

      // Screenshot after each step
      const safeName = `${flow.name}_step${i}_${step.action}`;
      screenshotPath = path.join(this.screenshotDir, `${safeName}.png`);
      try {
        await page.screenshot({ path: screenshotPath });
        screenshots.push(screenshotPath);
      } catch {
        screenshotPath = undefined;
      }

      stepResults.push({
        step,
        success,
        duration_ms: Date.now() - stepStart,
        error,
        screenshot_path: screenshotPath,
      });

      const icon = success ? 'PASS' : 'FAIL';
      console.log(`      ${icon} [${step.action}] ${step.description}${error ? ` — ${error}` : ''}`);

      // Stop flow on failure — subsequent steps likely depend on this one
      if (!success) break;
    }

    await page.close();

    return {
      flow_name: flow.name,
      steps: stepResults,
      screenshots,
      success: flowSuccess,
      duration_ms: Date.now() - flowStart,
    };
  }

  private interpolate(value: string): string {
    return value.replace(/\{timestamp\}/g, this.sessionTs);
  }

  private async executeStep(page: Page, step: BrowserStep): Promise<void> {
    const timeout = step.timeout || 10000;

    switch (step.action) {
      case 'goto': {
        const raw = step.url?.startsWith('http') ? step.url : `${this.baseUrl}${step.url}`;
        const url = this.interpolate(raw);
        await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
        // Extra wait for client-side hydration
        await page.waitForTimeout(1000);
        break;
      }

      case 'click': {
        if (!step.selector) throw new Error('click requires a selector');
        await page.waitForSelector(step.selector, { state: 'visible', timeout });
        await page.click(step.selector);
        // Wait for any navigation or rendering triggered by the click
        await page.waitForTimeout(500);
        break;
      }

      case 'fill': {
        if (!step.selector) throw new Error('fill requires a selector');
        if (step.value === undefined) throw new Error('fill requires a value');
        await page.waitForSelector(step.selector, { state: 'visible', timeout });
        await page.fill(step.selector, this.interpolate(step.value));
        break;
      }

      case 'select': {
        if (!step.selector) throw new Error('select requires a selector');
        if (step.value === undefined) throw new Error('select requires a value');
        await page.waitForSelector(step.selector, { state: 'visible', timeout });
        await page.selectOption(step.selector, step.value);
        break;
      }

      case 'wait': {
        if (step.selector) {
          await page.waitForSelector(step.selector, { state: 'visible', timeout });
        } else {
          await page.waitForTimeout(step.timeout || 2000);
        }
        break;
      }

      case 'screenshot': {
        // Handled by the caller after each step
        break;
      }

      case 'assert_visible': {
        if (!step.selector) throw new Error('assert_visible requires a selector');
        const el = await page.waitForSelector(step.selector, { state: 'visible', timeout });
        if (!el) throw new Error(`Element "${step.selector}" not visible`);
        break;
      }

      case 'assert_text': {
        if (!step.expected_text) throw new Error('assert_text requires expected_text');
        const bodyText = await page.evaluate(() => document.body.innerText);
        if (!bodyText.includes(step.expected_text)) {
          throw new Error(
            `Expected text "${step.expected_text}" not found on page. ` +
            `Page text starts with: "${bodyText.slice(0, 200)}..."`
          );
        }
        break;
      }

      default:
        throw new Error(`Unknown browser step action: ${step.action}`);
    }
  }
}
