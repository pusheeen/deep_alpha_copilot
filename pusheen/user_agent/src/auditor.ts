/**
 * Page auditor — fetches a page and analyzes its HTML for
 * accessibility, semantic structure, performance signals, and UX quality.
 */
import * as cheerio from 'cheerio';
import { timedFetch } from './fetcher.js';
import type { PageAudit } from './types.js';

export async function auditPage(baseUrl: string, path: string): Promise<PageAudit> {
  const url = `${baseUrl}${path}`;
  const result = await timedFetch(url);
  const $ = cheerio.load(result.body);

  // Headings
  const heading_count = $('h1, h2, h3, h4, h5, h6').length;

  // Links
  const link_count = $('a').length;

  // Images
  const images = $('img');
  const image_count = images.length;
  let images_without_alt = 0;
  images.each((_, el) => {
    if (!$(el).attr('alt')) images_without_alt++;
  });

  // Forms
  const form_count = $('form').length;
  const input_count = $('input, textarea, select').length;
  const button_count = $('button, input[type="submit"]').length;

  // Semantic HTML
  const has_nav = $('nav').length > 0;
  const has_footer = $('footer').length > 0;
  const uses_semantic_html =
    $('main, article, section, aside, header, footer, nav').length > 0;

  // Meta
  const title = $('title').text().trim();
  const has_meta_description = $('meta[name="description"]').length > 0;
  const has_viewport_meta = $('meta[name="viewport"]').length > 0;

  // ARIA
  let aria_attributes = 0;
  $('[aria-label], [aria-labelledby], [aria-describedby], [role]').each(() => {
    aria_attributes++;
  });

  // Interactive elements without labels
  let interactive_elements_without_labels = 0;
  $('input, textarea, select').each((_, el) => {
    const id = $(el).attr('id');
    const ariaLabel = $(el).attr('aria-label');
    const placeholder = $(el).attr('placeholder');
    const hasLabel = id ? $(`label[for="${id}"]`).length > 0 : false;
    if (!hasLabel && !ariaLabel && !placeholder) {
      interactive_elements_without_labels++;
    }
  });

  // JS & CSS
  const js_bundle_count = $('script[src]').length;
  const css_file_count = $('link[rel="stylesheet"]').length;
  const inline_style_count = $('[style]').length;

  // Text preview
  const bodyText = $('body').text().replace(/\s+/g, ' ').trim();
  const text_content_preview = bodyText.slice(0, 500);

  return {
    url: path,
    status: result.status,
    timing_ms: result.timing_ms,
    html_size_bytes: result.body.length,
    title,
    has_meta_description,
    has_viewport_meta,
    heading_count,
    link_count,
    image_count,
    images_without_alt,
    form_count,
    input_count,
    button_count,
    has_nav,
    has_footer,
    uses_semantic_html,
    color_contrast_issues: [],
    text_content_preview,
    js_bundle_count,
    css_file_count,
    inline_style_count,
    aria_attributes,
    interactive_elements_without_labels,
  };
}
