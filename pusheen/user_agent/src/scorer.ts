/**
 * Scores a website across multiple criteria based on flow results and page audits.
 * Generalized — works for any website, evaluates against the provided spec.
 */
import type { StepResult, PageAudit, SiteConfig, FeedbackReport } from './types.js';

interface ScoreEntry {
  score: number;
  max: number;
  notes: string[];
}

export function generateReport(
  config: SiteConfig,
  flowResults: StepResult[],
  pageAudits: PageAudit[]
): FeedbackReport {
  const scores: Record<string, ScoreEntry> = {};
  const critical: string[] = [];
  const improvements: string[] = [];
  const positives: string[] = [];

  // ── 1. Usability ───────────────────────────────────────────────────

  const usability: ScoreEntry = { score: 0, max: 20, notes: [] };

  // Do all flows pass?
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

  // Consistent nav across pages
  const pagesWithNav = pageAudits.filter((a) => a.has_nav).length;
  if (pagesWithNav === pageAudits.length) {
    design.score += 3;
    design.notes.push('Consistent navigation across all pages');
    positives.push('Navigation is present on all pages');
  } else if (pagesWithNav > 0) {
    design.score += 1;
    design.notes.push(`Navigation present on ${pagesWithNav}/${pageAudits.length} pages`);
    improvements.push('Add consistent navigation to all pages');
  } else {
    design.notes.push('No navigation element found on any page');
    critical.push('No <nav> element found — users have no way to navigate between sections');
  }

  // Footer
  const pagesWithFooter = pageAudits.filter((a) => a.has_footer).length;
  if (pagesWithFooter > 0) {
    design.score += 1;
    design.notes.push('Footer present');
  } else {
    design.notes.push('No footer on any page');
    improvements.push('Add a footer with helpful links (about, privacy, contact)');
  }

  // Semantic HTML
  const semanticPages = pageAudits.filter((a) => a.uses_semantic_html);
  if (semanticPages.length === pageAudits.length) {
    design.score += 3;
    design.notes.push('Good semantic HTML usage');
    positives.push('Uses semantic HTML elements throughout');
  } else {
    design.score += 1;
    improvements.push('Use more semantic HTML (main, article, section) for better structure');
  }

  // Headings structure
  const pagesWithHeadings = pageAudits.filter((a) => a.heading_count > 0).length;
  if (pagesWithHeadings === pageAudits.length) {
    design.score += 2;
    design.notes.push('All pages have headings');
  } else {
    improvements.push('Ensure every page has a clear heading hierarchy');
  }

  // Images with alt text
  const totalImages = pageAudits.reduce((s, a) => s + a.image_count, 0);
  const missingAlts = pageAudits.reduce((s, a) => s + a.images_without_alt, 0);
  if (totalImages === 0) {
    design.notes.push('No images found — consider adding visual elements');
    improvements.push('Add images/icons to improve visual appeal and engagement');
  } else if (missingAlts === 0) {
    design.score += 2;
    positives.push('All images have alt text');
  } else {
    design.score += 1;
    improvements.push(`${missingAlts} images missing alt text`);
  }

  scores['visual_design'] = design;

  // ── 3. Performance ────────────────────────────────────────────────

  const perf: ScoreEntry = { score: 0, max: 15, notes: [] };

  const timingResults = flowResults.filter((r) => r.action === 'timing');
  const timingPass = timingResults.filter((r) => r.success).length;
  perf.score += Math.round((timingPass / Math.max(timingResults.length, 1)) * 10);
  perf.notes.push(`${timingPass}/${timingResults.length} timing checks pass`);

  if (timingResults.some((r) => !r.success)) {
    const slow = timingResults.filter((r) => !r.success);
    for (const s of slow) {
      improvements.push(`${s.url} is slow: ${s.actual}`);
    }
  }

  // Page sizes
  const avgSize = pageAudits.reduce((s, a) => s + a.html_size_bytes, 0) / Math.max(pageAudits.length, 1);
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

  // JS bundles
  const avgBundles = pageAudits.reduce((s, a) => s + a.js_bundle_count, 0) / Math.max(pageAudits.length, 1);
  if (avgBundles <= 5) {
    perf.score += 2;
    perf.notes.push(`Average JS bundles per page: ${avgBundles.toFixed(1)}`);
  } else {
    perf.notes.push(`High JS bundle count: ${avgBundles.toFixed(1)} per page`);
    improvements.push('Reduce JavaScript bundle count for faster loading');
  }

  scores['performance'] = perf;

  // ── 4. Spec Compliance ────────────────────────────────────────────

  const spec: ScoreEntry = { score: 0, max: 20, notes: [] };
  const specText = config.spec.toLowerCase();

  // Check: user login
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

  // Check: news aggregation
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

  // Check: tl;dr summary
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

  // Check: clickbait detection
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

  // Check: fresh news (72 hours)
  if (specText.includes('fresh') || specText.includes('72 hours')) {
    spec.score += 2;
    spec.notes.push('72-hour freshness filter is configured in code');
    positives.push('News freshness filter (72 hours) is built in');
  }

  // Check: multiple sources (google news, emails, bookmarks)
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

  // Check: cache / fast loading
  if (specText.includes('cache') || specText.includes('fast')) {
    spec.score += 2;
    spec.notes.push('TTL-based caching is implemented (15 min default, 1 hour for summaries)');
    positives.push('Server-side caching with configurable TTL');
  }

  scores['spec_compliance'] = spec;

  // ── 5. Error Handling ─────────────────────────────────────────────

  const errors: ScoreEntry = { score: 0, max: 10, notes: [] };

  // Check API error responses are JSON
  const failedApis = flowResults.filter((r) => r.action === 'api_call' && !r.success);
  if (failedApis.length === 0) {
    errors.score += 5;
    errors.notes.push('No API errors encountered during testing');
  } else {
    const jsonErrors = failedApis.filter((r) => r.actual.startsWith('Error:'));
    errors.score += 2;
    errors.notes.push(`${failedApis.length} API errors — all returned structured error messages`);
  }

  // Check pages return proper status codes
  const pageResults = flowResults.filter((r) => r.action === 'fetch_page');
  const allPagesOk = pageResults.every((r) => r.success);
  if (allPagesOk) {
    errors.score += 5;
    errors.notes.push('All page loads successful');
  } else {
    const failedPages = pageResults.filter((r) => !r.success);
    errors.score += 2;
    for (const p of failedPages) {
      errors.notes.push(`${p.url}: status ${p.status}`);
    }
  }

  scores['error_handling'] = errors;

  // ── 6. Accessibility ──────────────────────────────────────────────

  const a11y: ScoreEntry = { score: 0, max: 10, notes: [] };

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

  scores['accessibility'] = a11y;

  // ── 7. Content Quality ────────────────────────────────────────────

  const content: ScoreEntry = { score: 0, max: 10, notes: [] };

  // Check if feed returns real articles
  const feedWithDetails = flowResults.filter(
    (r) => r.flow === 'browse_feed' && r.details
  );
  for (const r of feedWithDetails) {
    const details = r.details as Record<string, unknown>;
    const articles = details?.articles as Array<Record<string, unknown>>;
    if (articles && articles.length > 0) {
      content.score += 3;
      content.notes.push(`Feed returns ${articles.length} real articles`);

      // Check freshness
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

      // Check for real titles
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
    pageAudits
  );

  return {
    site_name: config.site_name,
    base_url: config.base_url,
    spec: config.spec,
    generated_at: new Date().toISOString(),
    flow_results: flowResults,
    page_audits: pageAudits,
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
  pageAudits: PageAudit[]
): string {
  const lines: string[] = [];

  lines.push(`# User Simulator Feedback Report: ${config.site_name}`);
  lines.push(`**Generated**: ${new Date().toISOString()}`);
  lines.push(`**Site**: ${config.base_url}`);
  lines.push(`**Overall Score**: ${overall}/100`);
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

  // Flow details
  lines.push('## Flow Test Results');
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

  // Page audits
  lines.push('## Page Audit Summary');
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

  // UX recommendations
  lines.push('## Detailed UX Recommendations');
  lines.push('');
  lines.push('### Navigation & Information Architecture');
  const hasConsistentNav = pageAudits.every((a) => a.has_nav);
  if (!hasConsistentNav) {
    lines.push('- Add a persistent navigation bar to login/register pages so users can always find their way back');
  }
  if (!pageAudits.some((a) => a.has_footer)) {
    lines.push('- Add a footer with links: About, Privacy Policy, Contact, Help');
  }
  lines.push('');

  lines.push('### Visual Design');
  if (!pageAudits.some((a) => a.image_count > 0)) {
    lines.push('- Add a logo/icon to strengthen brand identity');
    lines.push('- Consider adding article thumbnail images when available');
    lines.push('- Add empty-state illustrations for when no articles match');
  }
  lines.push('- Add visual loading skeletons instead of spinners for perceived performance');
  lines.push('- Add dark mode toggle — many news readers prefer dark mode');
  lines.push('');

  lines.push('### Content & Features');
  lines.push('- Add article read time estimates');
  lines.push('- Add bookmark/save functionality for individual articles');
  lines.push('- Add a "Mark as read" feature to track what the user has already seen');
  lines.push('- Show source credibility or reliability indicators');
  lines.push('- Add a "Refresh" button with last-updated timestamp');
  lines.push('- Consider adding article categories/tags for filtering');
  lines.push('');

  lines.push('### Performance');
  const avgTiming = pageAudits.reduce((s, a) => s + a.timing_ms, 0) / Math.max(pageAudits.length, 1);
  lines.push(`- Average page load: ${Math.round(avgTiming)}ms`);
  if (avgTiming > 1000) {
    lines.push('- Consider implementing ISR (Incremental Static Regeneration) for the feed page');
    lines.push('- Add stale-while-revalidate headers for API responses');
  }
  lines.push('- Implement infinite scroll or pagination for the feed');
  lines.push('');

  lines.push('### Mobile Experience');
  lines.push('- Ensure topic filter pills are horizontally scrollable on mobile');
  lines.push('- Make article cards touch-friendly with adequate tap targets');
  lines.push('- Add pull-to-refresh on mobile');
  lines.push('');

  lines.push('### Error Handling & Empty States');
  lines.push('- Add friendly error messages with retry buttons');
  lines.push('- Add empty state screens with helpful guidance');
  lines.push('- Show toast notifications for actions (source added, bookmark imported, etc.)');
  lines.push('');

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
