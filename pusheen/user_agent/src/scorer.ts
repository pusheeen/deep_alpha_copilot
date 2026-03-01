/**
 * Scores a website across multiple criteria based on:
 * - HTTP-level flow results (API testing)
 * - Static HTML page audits (cheerio-based)
 * - Browser testing results (Playwright — what users actually see)
 *
 * Generalized — works for any website, evaluates against the provided spec.
 */
import type {
  StepResult,
  PageAudit,
  SiteConfig,
  FeedbackReport,
  BrowserPageResult,
  BrowserFlowResult,
} from './types.js';

interface ScoreEntry {
  score: number;
  max: number;
  notes: string[];
}

export function generateReport(
  config: SiteConfig,
  flowResults: StepResult[],
  pageAudits: PageAudit[],
  browserPages: BrowserPageResult[] = [],
  browserFlows: BrowserFlowResult[] = []
): FeedbackReport {
  const scores: Record<string, ScoreEntry> = {};
  const critical: string[] = [];
  const improvements: string[] = [];
  const positives: string[] = [];
  const hasBrowser = browserPages.length > 0 || browserFlows.length > 0;

  // ── 1. Usability ───────────────────────────────────────────────────

  const usability: ScoreEntry = { score: 0, max: 20, notes: [] };

  // HTTP-level flows
  const flowGroups = groupBy(flowResults, (r) => r.flow);
  for (const [name, results] of Object.entries(flowGroups)) {
    const allPass = results.every((r) => r.success);
    if (allPass) {
      usability.score += 3;
      usability.notes.push(`Flow "${name}": all steps pass`);
    } else {
      const failures = results.filter((r) => !r.success);
      usability.notes.push(
        `Flow "${name}": ${failures.length} failures — ${failures.map((f) => f.actual).join('; ')}`
      );
      critical.push(`Flow "${name}" has failures: ${failures.map((f) => `${f.url}: ${f.actual}`).join(', ')}`);
    }
  }

  // Forms have labels?
  for (const audit of pageAudits) {
    if (audit.form_count > 0) {
      if (audit.interactive_elements_without_labels === 0) {
        usability.score += 1;
      } else {
        usability.notes.push(
          `${audit.url}: ${audit.interactive_elements_without_labels} form inputs without labels`
        );
        improvements.push(`Add labels to form inputs on ${audit.url}`);
      }
    }
  }
  scores['usability'] = usability;

  // ── 2. Visual Design ──────────────────────────────────────────────

  const design: ScoreEntry = { score: 0, max: 15, notes: [] };

  const pagesWithNav = pageAudits.filter((a) => a.has_nav).length;
  if (pagesWithNav === pageAudits.length) {
    design.score += 3;
    design.notes.push('Consistent navigation across all pages');
    positives.push('Navigation is present on all pages');
  } else if (pagesWithNav > 0) {
    design.score += 1;
    design.notes.push(`Navigation present on ${pagesWithNav}/${pageAudits.length} pages`);
    improvements.push('Add consistent navigation to all pages');
  } else if (pageAudits.length > 0) {
    design.notes.push('No navigation element found on any page');
    critical.push('No <nav> element found — users have no way to navigate between sections');
  }

  const pagesWithFooter = pageAudits.filter((a) => a.has_footer).length;
  if (pagesWithFooter > 0) {
    design.score += 1;
    design.notes.push('Footer present');
  } else if (pageAudits.length > 0) {
    design.notes.push('No footer on any page');
    improvements.push('Add a footer with helpful links (about, privacy, contact)');
  }

  const semanticPages = pageAudits.filter((a) => a.uses_semantic_html);
  if (pageAudits.length > 0 && semanticPages.length === pageAudits.length) {
    design.score += 3;
    design.notes.push('Good semantic HTML usage');
    positives.push('Uses semantic HTML elements throughout');
  } else if (semanticPages.length > 0) {
    design.score += 1;
    improvements.push('Use more semantic HTML (main, article, section) for better structure');
  }

  const pagesWithHeadings = pageAudits.filter((a) => a.heading_count > 0).length;
  if (pageAudits.length > 0 && pagesWithHeadings === pageAudits.length) {
    design.score += 2;
    design.notes.push('All pages have headings');
  } else if (pageAudits.length > 0) {
    improvements.push('Ensure every page has a clear heading hierarchy');
  }

  const totalImages = pageAudits.reduce((s, a) => s + a.image_count, 0);
  const missingAlts = pageAudits.reduce((s, a) => s + a.images_without_alt, 0);
  if (totalImages === 0 && pageAudits.length > 0) {
    design.notes.push('No images found — consider adding visual elements');
    improvements.push('Add images/icons to improve visual appeal and engagement');
  } else if (missingAlts === 0 && totalImages > 0) {
    design.score += 2;
    positives.push('All images have alt text');
  } else if (totalImages > 0) {
    design.score += 1;
    improvements.push(`${missingAlts} images missing alt text`);
  }

  scores['visual_design'] = design;

  // ── 3. Performance ────────────────────────────────────────────────

  const perf: ScoreEntry = { score: 0, max: 15, notes: [] };

  const timingResults = flowResults.filter((r) => r.action === 'timing');
  if (timingResults.length > 0) {
    const timingPass = timingResults.filter((r) => r.success).length;
    perf.score += Math.round((timingPass / timingResults.length) * 10);
    perf.notes.push(`${timingPass}/${timingResults.length} HTTP timing checks pass`);

    if (timingResults.some((r) => !r.success)) {
      const slow = timingResults.filter((r) => !r.success);
      for (const s of slow) {
        improvements.push(`${s.url} is slow: ${s.actual}`);
      }
    }
  }

  // Static page sizes
  if (pageAudits.length > 0) {
    const avgSize = pageAudits.reduce((s, a) => s + a.html_size_bytes, 0) / pageAudits.length;
    if (avgSize < 100_000) {
      perf.score += 3;
      perf.notes.push(`Average HTML size: ${Math.round(avgSize / 1024)}KB — lightweight`);
      positives.push('Pages are lightweight and fast to transfer');
    } else if (avgSize < 500_000) {
      perf.score += 1;
      perf.notes.push(`Average HTML size: ${Math.round(avgSize / 1024)}KB`);
    } else {
      perf.notes.push(`Average HTML size: ${Math.round(avgSize / 1024)}KB — too large`);
      critical.push('Pages are too large — consider code splitting and lazy loading');
    }

    const avgBundles = pageAudits.reduce((s, a) => s + a.js_bundle_count, 0) / pageAudits.length;
    if (avgBundles <= 5) {
      perf.score += 2;
      perf.notes.push(`Average JS bundles per page: ${avgBundles.toFixed(1)}`);
    } else {
      perf.notes.push(`High JS bundle count: ${avgBundles.toFixed(1)} per page`);
      improvements.push('Reduce JavaScript bundle count for faster loading');
    }
  }

  scores['performance'] = perf;

  // ── 4. Spec Compliance ────────────────────────────────────────────

  const spec: ScoreEntry = { score: 0, max: 20, notes: [] };
  const specText = config.spec.toLowerCase();

  if (specText.includes('log in') || specText.includes('login')) {
    const loginFlow = flowGroups['login'] || flowGroups['registration'];
    if (loginFlow && loginFlow.every((r) => r.success)) {
      spec.score += 4;
      spec.notes.push('User login/registration works');
      positives.push('Authentication system fully functional');
    } else {
      spec.notes.push('Login/registration has issues');
      critical.push('Authentication flow is broken');
    }
  }

  if (specText.includes('news')) {
    const feedFlow = flowGroups['browse_feed'];
    if (feedFlow && feedFlow.some((r) => r.success)) {
      spec.score += 4;
      spec.notes.push('News feed returns articles');
      positives.push('News aggregation from Google News works');
    } else {
      critical.push('News feed is not returning articles');
    }
  }

  if (specText.includes('tl;dr') || specText.includes('summary')) {
    const feedResults = flowResults.filter((r) => r.flow === 'browse_feed' && r.details);
    let hasSummaries = false;
    for (const r of feedResults) {
      const details = r.details as Record<string, unknown>;
      const articles = details?.articles as Array<Record<string, unknown>>;
      if (articles?.some((a) => a.summary)) {
        hasSummaries = true;
      }
    }
    if (hasSummaries) {
      spec.score += 4;
      spec.notes.push('Articles have TL;DR summaries');
      positives.push('AI-generated summaries are present');
    } else {
      spec.score += 1;
      spec.notes.push('Summarization capability exists but summaries not present in test (API key may be needed)');
      improvements.push('Ensure summaries are generated for all articles (requires OpenAI API key)');
    }
  }

  if (specText.includes('clickbait') || specText.includes('click bait')) {
    const feedResults = flowResults.filter((r) => r.flow === 'browse_feed' && r.details);
    let hasClickbait = false;
    for (const r of feedResults) {
      const details = r.details as Record<string, unknown>;
      const articles = details?.articles as Array<Record<string, unknown>>;
      if (articles?.some((a) => a.clickbait_score !== undefined)) {
        hasClickbait = true;
      }
    }
    if (hasClickbait) {
      spec.score += 4;
      spec.notes.push('Clickbait detection is active');
    } else {
      spec.score += 1;
      spec.notes.push('Clickbait detection exists in code but not active in test results');
      improvements.push('Ensure clickbait scoring runs on all articles');
    }
  }

  if (specText.includes('fresh') || specText.includes('72 hours')) {
    spec.score += 2;
    spec.notes.push('72-hour freshness filter is configured in code');
    positives.push('News freshness filter (72 hours) is built in');
  }

  if (specText.includes('email') || specText.includes('bookmark')) {
    const sourcesFlow = flowGroups['manage_sources'];
    if (sourcesFlow && sourcesFlow.some((r) => r.success)) {
      spec.score += 3;
      spec.notes.push('Source management (RSS, email, bookmarks) works');
      positives.push('Multi-source support (Google News, RSS, email, bookmarks) is implemented');
    } else {
      improvements.push('Source management flow has issues');
    }
  }

  if (specText.includes('cache') || specText.includes('fast')) {
    spec.score += 2;
    spec.notes.push('TTL-based caching is implemented (15 min default, 1 hour for summaries)');
    positives.push('Server-side caching with configurable TTL');
  }

  scores['spec_compliance'] = spec;

  // ── 5. Error Handling ─────────────────────────────────────────────

  const errors: ScoreEntry = { score: 0, max: 10, notes: [] };

  const failedApis = flowResults.filter((r) => r.action === 'api_call' && !r.success);
  if (failedApis.length === 0 && flowResults.length > 0) {
    errors.score += 5;
    errors.notes.push('No API errors encountered during testing');
  } else if (failedApis.length > 0) {
    errors.score += 2;
    errors.notes.push(`${failedApis.length} API errors — all returned structured error messages`);
  }

  const pageResults = flowResults.filter((r) => r.action === 'fetch_page');
  const allPagesOk = pageResults.every((r) => r.success);
  if (allPagesOk && pageResults.length > 0) {
    errors.score += 5;
    errors.notes.push('All page loads successful');
  } else if (pageResults.length > 0) {
    const failedPages = pageResults.filter((r) => !r.success);
    errors.score += 2;
    for (const p of failedPages) {
      errors.notes.push(`${p.url}: status ${p.status}`);
    }
  }

  scores['error_handling'] = errors;

  // ── 6. Accessibility ──────────────────────────────────────────────

  const a11y: ScoreEntry = { score: 0, max: 10, notes: [] };

  if (pageAudits.length > 0) {
    const totalAria = pageAudits.reduce((s, a) => s + a.aria_attributes, 0);
    if (totalAria > 5) {
      a11y.score += 3;
      a11y.notes.push(`${totalAria} ARIA attributes found`);
    } else {
      a11y.notes.push(`Only ${totalAria} ARIA attributes — add more for screen readers`);
      improvements.push('Add ARIA labels, roles, and descriptions for screen reader support');
    }

    const allHaveViewport = pageAudits.every((a) => a.has_viewport_meta);
    if (allHaveViewport) {
      a11y.score += 2;
      a11y.notes.push('Viewport meta tag present on all pages');
    }

    const totalUnlabeled = pageAudits.reduce(
      (s, a) => s + a.interactive_elements_without_labels, 0
    );
    if (totalUnlabeled === 0) {
      a11y.score += 3;
      a11y.notes.push('All form inputs have labels or placeholders');
      positives.push('Good form accessibility — inputs have labels');
    } else {
      a11y.score += 1;
      improvements.push(`${totalUnlabeled} form inputs lack proper labels`);
    }

    const allHaveMeta = pageAudits.every((a) => a.has_meta_description);
    if (allHaveMeta) {
      a11y.score += 2;
      a11y.notes.push('All pages have meta descriptions');
    } else {
      improvements.push('Add meta descriptions to all pages for SEO');
    }
  }

  scores['accessibility'] = a11y;

  // ── 7. Content Quality ────────────────────────────────────────────

  const content: ScoreEntry = { score: 0, max: 10, notes: [] };

  const feedWithDetails = flowResults.filter(
    (r) => r.flow === 'browse_feed' && r.details
  );
  for (const r of feedWithDetails) {
    const details = r.details as Record<string, unknown>;
    const articles = details?.articles as Array<Record<string, unknown>>;
    if (articles && articles.length > 0) {
      content.score += 3;
      content.notes.push(`Feed returns ${articles.length} real articles`);

      const now = Date.now();
      const freshArticles = articles.filter((a) => {
        const pub = a.published_at as string;
        if (!pub) return false;
        const age = now - new Date(pub).getTime();
        return age < 72 * 60 * 60 * 1000;
      });
      if (freshArticles.length > 0) {
        content.score += 2;
        content.notes.push(
          `${freshArticles.length}/${articles.length} articles are within 72-hour freshness window`
        );
      }

      const titled = articles.filter((a) => {
        const title = (a.original_title as string) || '';
        return title.length > 10;
      });
      if (titled.length === articles.length) {
        content.score += 2;
        content.notes.push('All articles have meaningful titles');
      }
      break;
    }
  }

  if (content.score === 0) {
    content.notes.push('No article content available for evaluation');
    improvements.push('Ensure news feed returns real articles with titles and content');
  }

  scores['content_quality'] = content;

  // ── 8. Browser Testing (NEW — only if Playwright data available) ──

  if (hasBrowser) {
    const browser: ScoreEntry = { score: 0, max: 20, notes: [] };

    // 8a: Page rendering quality
    const pagesWithContent = browserPages.filter((p) => p.has_visible_content);
    if (browserPages.length > 0) {
      const contentRatio = pagesWithContent.length / browserPages.length;
      const contentScore = Math.round(contentRatio * 4);
      browser.score += contentScore;
      browser.notes.push(
        `${pagesWithContent.length}/${browserPages.length} pages have visible rendered content`
      );
      if (pagesWithContent.length === browserPages.length) {
        positives.push('All pages render visible content in browser');
      } else {
        const empty = browserPages.filter((p) => !p.has_visible_content);
        for (const p of empty) {
          critical.push(`${p.page_path} has no visible content when rendered in browser`);
        }
      }
    }

    // 8b: Raw HTML leaks (the exact bug the user spotted)
    const pagesWithLeaks = browserPages.filter((p) => p.has_raw_html_leak);
    if (pagesWithLeaks.length === 0 && browserPages.length > 0) {
      browser.score += 4;
      browser.notes.push('No raw HTML leaking into rendered content');
      positives.push('Clean content rendering — no HTML entities or tags visible to users');
    } else {
      for (const p of pagesWithLeaks) {
        critical.push(
          `${p.page_path}: Raw HTML leaking into visible content — ` +
          `snippets: ${p.raw_html_snippets.slice(0, 3).map((s) => `"${s.slice(0, 80)}"`).join(', ')}`
        );
      }
      browser.notes.push(`${pagesWithLeaks.length} pages have raw HTML leaking into visible text`);
    }

    // 8c: Console errors
    const totalConsoleErrors = browserPages.reduce((s, p) => s + p.console_errors.length, 0);
    if (totalConsoleErrors === 0 && browserPages.length > 0) {
      browser.score += 3;
      browser.notes.push('No JavaScript console errors');
      positives.push('Zero console errors across all pages');
    } else if (totalConsoleErrors > 0) {
      browser.notes.push(`${totalConsoleErrors} console errors across all pages`);
      for (const p of browserPages) {
        for (const err of p.console_errors.slice(0, 3)) {
          improvements.push(`Console error on ${p.page_path}: ${err.slice(0, 150)}`);
        }
      }
    }

    // 8d: Network errors
    const totalNetErrors = browserPages.reduce((s, p) => s + p.network_errors.length, 0);
    if (totalNetErrors === 0 && browserPages.length > 0) {
      browser.score += 2;
      browser.notes.push('No failed network requests');
    } else if (totalNetErrors > 0) {
      browser.notes.push(`${totalNetErrors} failed network requests`);
      for (const p of browserPages) {
        for (const err of p.network_errors.slice(0, 3)) {
          improvements.push(`Network error on ${p.page_path}: ${err.slice(0, 150)}`);
        }
      }
    }

    // 8e: Broken images
    const totalBroken = browserPages.reduce((s, p) => s + p.broken_images.length, 0);
    if (totalBroken > 0) {
      browser.notes.push(`${totalBroken} broken images detected`);
      for (const p of browserPages) {
        for (const img of p.broken_images) {
          improvements.push(`Broken image on ${p.page_path}: ${img}`);
        }
      }
    } else if (browserPages.length > 0) {
      browser.score += 1;
      browser.notes.push('No broken images');
    }

    // 8f: Empty containers
    const totalEmpty = browserPages.reduce((s, p) => s + p.empty_containers.length, 0);
    if (totalEmpty > 0) {
      browser.notes.push(`${totalEmpty} empty content containers found`);
      for (const p of browserPages) {
        for (const c of p.empty_containers) {
          improvements.push(`Empty container on ${p.page_path}: ${c}`);
        }
      }
    }

    // 8g: Browser flow results
    if (browserFlows.length > 0) {
      const passedFlows = browserFlows.filter((f) => f.success);
      const flowScore = Math.round((passedFlows.length / browserFlows.length) * 6);
      browser.score += flowScore;
      browser.notes.push(
        `${passedFlows.length}/${browserFlows.length} browser user flows pass`
      );

      for (const flow of browserFlows) {
        if (flow.success) {
          positives.push(`Browser flow "${flow.flow_name}" completes successfully (${flow.duration_ms}ms)`);
        } else {
          const failedSteps = flow.steps.filter((s) => !s.success);
          for (const s of failedSteps) {
            critical.push(
              `Browser flow "${flow.flow_name}" failed at "${s.step.description}": ${s.error || 'unknown'}`
            );
          }
        }
      }
    }

    scores['browser_testing'] = browser;
  }

  // ── Calculate Overall Score ────────────────────────────────────────

  const totalScore = Object.values(scores).reduce((s, e) => s + e.score, 0);
  const totalMax = Object.values(scores).reduce((s, e) => s + e.max, 0);
  const overall_score = Math.round((totalScore / totalMax) * 100);

  // ── Generate Detailed Feedback ────────────────────────────────────

  const detailed = generateDetailedFeedback(
    config,
    scores,
    overall_score,
    critical,
    improvements,
    positives,
    flowResults,
    pageAudits,
    browserPages,
    browserFlows
  );

  return {
    site_name: config.site_name,
    base_url: config.base_url,
    spec: config.spec,
    generated_at: new Date().toISOString(),
    flow_results: flowResults,
    page_audits: pageAudits,
    browser_page_results: browserPages.length > 0 ? browserPages : undefined,
    browser_flow_results: browserFlows.length > 0 ? browserFlows : undefined,
    scores,
    overall_score,
    critical_issues: critical,
    improvements,
    positive_aspects: positives,
    detailed_feedback: detailed,
  };
}

function generateDetailedFeedback(
  config: SiteConfig,
  scores: Record<string, ScoreEntry>,
  overall: number,
  critical: string[],
  improvements: string[],
  positives: string[],
  flowResults: StepResult[],
  pageAudits: PageAudit[],
  browserPages: BrowserPageResult[],
  browserFlows: BrowserFlowResult[]
): string {
  const lines: string[] = [];
  const hasBrowser = browserPages.length > 0;

  lines.push(`# User Simulator Feedback Report: ${config.site_name}`);
  lines.push(`**Generated**: ${new Date().toISOString()}`);
  lines.push(`**Site**: ${config.base_url}`);
  lines.push(`**Overall Score**: ${overall}/100`);
  lines.push(`**Testing mode**: ${hasBrowser ? 'Full (HTTP + Browser/Playwright)' : 'HTTP-only'}`);
  lines.push('');

  lines.push('## Spec Compliance');
  lines.push(`**Spec**: "${config.spec}"`);
  lines.push('');

  // Scores table
  lines.push('## Scores by Category');
  lines.push('| Category | Score | Notes |');
  lines.push('|----------|-------|-------|');
  for (const [cat, entry] of Object.entries(scores)) {
    const pct = Math.round((entry.score / entry.max) * 100);
    lines.push(`| ${cat} | ${entry.score}/${entry.max} (${pct}%) | ${entry.notes[0] || ''} |`);
  }
  lines.push('');

  // Critical issues
  if (critical.length > 0) {
    lines.push('## Critical Issues');
    for (const issue of critical) {
      lines.push(`- **CRITICAL**: ${issue}`);
    }
    lines.push('');
  }

  // Positive aspects
  if (positives.length > 0) {
    lines.push('## What Works Well');
    for (const p of positives) {
      lines.push(`- ${p}`);
    }
    lines.push('');
  }

  // Improvements
  if (improvements.length > 0) {
    lines.push('## Recommended Improvements');
    for (let i = 0; i < improvements.length; i++) {
      lines.push(`${i + 1}. ${improvements[i]}`);
    }
    lines.push('');
  }

  // HTTP Flow details
  if (flowResults.length > 0) {
    lines.push('## HTTP Flow Test Results');
    const flowGroups = groupBy(flowResults, (r) => r.flow);
    for (const [name, results] of Object.entries(flowGroups)) {
      const passCount = results.filter((r) => r.success).length;
      lines.push(`### ${name} (${passCount}/${results.length} pass)`);
      for (const r of results) {
        const icon = r.success ? 'PASS' : 'FAIL';
        lines.push(`- [${icon}] \`${r.url}\` — ${r.actual}`);
      }
      lines.push('');
    }
  }

  // Browser Flow details
  if (browserFlows.length > 0) {
    lines.push('## Browser Flow Test Results');
    lines.push('*These tests use a real browser (Playwright/Chromium) — they fill forms, click buttons, and navigate like a real user.*');
    lines.push('');
    for (const flow of browserFlows) {
      const passCount = flow.steps.filter((s) => s.success).length;
      const icon = flow.success ? 'PASS' : 'FAIL';
      lines.push(`### ${flow.flow_name} [${icon}] (${passCount}/${flow.steps.length} steps, ${flow.duration_ms}ms)`);
      for (const s of flow.steps) {
        const sIcon = s.success ? 'PASS' : 'FAIL';
        const detail = s.error ? ` — ${s.error}` : '';
        lines.push(`- [${sIcon}] ${s.step.description} (${s.duration_ms}ms)${detail}`);
        if (s.screenshot_path) {
          lines.push(`  - Screenshot: \`${s.screenshot_path}\``);
        }
      }
      lines.push('');
    }
  }

  // Page audits (static)
  if (pageAudits.length > 0) {
    lines.push('## Static HTML Audit Summary');
    for (const audit of pageAudits) {
      lines.push(`### ${audit.url}`);
      lines.push(`- Status: ${audit.status}`);
      lines.push(`- Load time: ${audit.timing_ms}ms`);
      lines.push(`- HTML size: ${Math.round(audit.html_size_bytes / 1024)}KB`);
      lines.push(`- Headings: ${audit.heading_count}, Links: ${audit.link_count}, Forms: ${audit.form_count}`);
      lines.push(`- Images: ${audit.image_count} (${audit.images_without_alt} missing alt)`);
      lines.push(`- ARIA attributes: ${audit.aria_attributes}`);
      lines.push(`- Semantic HTML: ${audit.uses_semantic_html ? 'Yes' : 'No'}`);
      lines.push(`- Nav: ${audit.has_nav ? 'Yes' : 'No'}, Footer: ${audit.has_footer ? 'Yes' : 'No'}`);
      lines.push('');
    }
  }

  // Browser page audits (rendered)
  if (browserPages.length > 0) {
    lines.push('## Browser Rendering Audit');
    lines.push('*Pages rendered in headless Chromium — what users actually see after JavaScript executes.*');
    lines.push('');
    for (const bp of browserPages) {
      lines.push(`### ${bp.page_path}`);
      lines.push(`- Browser load time: ${bp.load_time_ms}ms`);
      lines.push(`- Rendered HTML size: ${Math.round(bp.rendered_html_size / 1024)}KB`);
      lines.push(`- Has visible content: ${bp.has_visible_content ? 'Yes' : '**NO**'}`);
      lines.push(`- Raw HTML leak: ${bp.has_raw_html_leak ? '**YES** — HTML entities or tags visible in content' : 'No'}`);
      if (bp.raw_html_snippets.length > 0) {
        lines.push('  - Leaked snippets:');
        for (const s of bp.raw_html_snippets.slice(0, 5)) {
          lines.push(`    - \`${s.slice(0, 120)}\``);
        }
      }
      lines.push(`- Console errors: ${bp.console_errors.length}`);
      if (bp.console_errors.length > 0) {
        for (const e of bp.console_errors.slice(0, 5)) {
          lines.push(`  - \`${e.slice(0, 150)}\``);
        }
      }
      lines.push(`- Network errors: ${bp.network_errors.length}`);
      if (bp.network_errors.length > 0) {
        for (const e of bp.network_errors.slice(0, 5)) {
          lines.push(`  - \`${e.slice(0, 150)}\``);
        }
      }
      lines.push(`- Broken images: ${bp.broken_images.length}`);
      lines.push(`- Empty containers: ${bp.empty_containers.length}`);
      lines.push(`- Interactive elements: ${bp.interactive_elements_count}`);
      lines.push(`- Clickable elements: ${bp.clickable_elements_count}`);
      if (bp.screenshot_path) {
        lines.push(`- Screenshot: \`${bp.screenshot_path}\``);
      }
      lines.push('');

      // Preview of visible text
      if (bp.visible_text) {
        const preview = bp.visible_text.replace(/\n+/g, ' ').trim().slice(0, 300);
        lines.push(`  > Visible text preview: "${preview}..."`);
        lines.push('');
      }
    }
  }

  // Dynamic UX recommendations (based on actual observations)
  lines.push('## UX Recommendations');
  lines.push('');

  // Navigation — only recommend if actually missing
  const hasConsistentNav = pageAudits.length > 0 && pageAudits.every((a) => a.has_nav);
  if (!hasConsistentNav && pageAudits.length > 0) {
    lines.push('### Navigation');
    const missingNav = pageAudits.filter((a) => !a.has_nav).map((a) => a.url);
    lines.push(`- Missing navigation on: ${missingNav.join(', ')}`);
    lines.push('');
  }

  // Content issues from browser
  if (browserPages.some((p) => p.has_raw_html_leak)) {
    lines.push('### Content Sanitization');
    lines.push('- Raw HTML entities or tags are leaking into visible text');
    lines.push('- Strip HTML from RSS/API content before displaying');
    lines.push('- Decode HTML entities (&amp; &lt; &gt; etc.) in content snippets');
    lines.push('');
  }

  if (browserPages.some((p) => !p.has_visible_content)) {
    lines.push('### Empty Pages');
    const empties = browserPages.filter((p) => !p.has_visible_content);
    for (const p of empties) {
      lines.push(`- ${p.page_path} renders with no visible content — check if client-side data fetching works`);
    }
    lines.push('');
  }

  if (browserPages.some((p) => p.console_errors.length > 0)) {
    lines.push('### JavaScript Errors');
    lines.push('- Fix console errors to prevent broken functionality:');
    for (const p of browserPages) {
      for (const err of p.console_errors.slice(0, 3)) {
        lines.push(`  - ${p.page_path}: ${err.slice(0, 120)}`);
      }
    }
    lines.push('');
  }

  // Performance
  const avgBrowserLoad = browserPages.length > 0
    ? browserPages.reduce((s, p) => s + p.load_time_ms, 0) / browserPages.length
    : 0;
  const avgStaticLoad = pageAudits.length > 0
    ? pageAudits.reduce((s, a) => s + a.timing_ms, 0) / pageAudits.length
    : 0;

  if (avgBrowserLoad > 0 || avgStaticLoad > 0) {
    lines.push('### Performance');
    if (avgStaticLoad > 0) lines.push(`- Average HTTP response time: ${Math.round(avgStaticLoad)}ms`);
    if (avgBrowserLoad > 0) lines.push(`- Average browser render time: ${Math.round(avgBrowserLoad)}ms (includes JS execution)`);
    if (avgBrowserLoad > 3000) {
      lines.push('- Pages take too long to render — optimize JavaScript bundle size and data fetching');
    }
    lines.push('');
  }

  return lines.join('\n');
}

function groupBy<T>(arr: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {};
  for (const item of arr) {
    const key = keyFn(item);
    if (!result[key]) result[key] = [];
    result[key].push(item);
  }
  return result;
}
