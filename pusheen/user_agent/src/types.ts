export interface BrowserFlow {
  name: string;
  steps: BrowserStep[];
}

export interface BrowserStep {
  action: 'goto' | 'click' | 'fill' | 'wait' | 'screenshot' | 'assert_visible' | 'assert_text' | 'select';
  /** CSS selector for click/fill/assert targets */
  selector?: string;
  /** Value for fill actions */
  value?: string;
  /** URL for goto actions */
  url?: string;
  /** Description of what this step does */
  description: string;
  /** Milliseconds for wait actions */
  timeout?: number;
  /** Expected text for assert_text */
  expected_text?: string;
}

export interface BrowserPageResult {
  url: string;
  page_path: string;
  screenshot_path: string | null;
  load_time_ms: number;
  console_errors: string[];
  console_warnings: string[];
  network_errors: string[];
  visible_text: string;
  rendered_html_size: number;
  has_visible_content: boolean;
  has_raw_html_leak: boolean;
  raw_html_snippets: string[];
  broken_images: string[];
  overlapping_elements: string[];
  empty_containers: string[];
  interactive_elements_count: number;
  clickable_elements_count: number;
}

export interface BrowserFlowResult {
  flow_name: string;
  steps: BrowserStepResult[];
  screenshots: string[];
  success: boolean;
  duration_ms: number;
}

export interface BrowserStepResult {
  step: BrowserStep;
  success: boolean;
  duration_ms: number;
  error?: string;
  screenshot_path?: string;
}

export interface SiteConfig {
  site_name: string;
  base_url: string;
  spec: string;
  flows: Flow[];
  browser_flows?: BrowserFlow[];
  pages_to_audit: string[];
  evaluation_criteria: string[];
}

export interface Flow {
  name: string;
  steps: FlowStep[];
}

export interface FlowStep {
  action: 'fetch_page' | 'api_call' | 'timing';
  method?: string;
  url: string;
  body?: Record<string, unknown>;
  auth?: boolean;
  save_token?: boolean;
  expect: string;
}

export interface StepResult {
  flow: string;
  step: string;
  action: string;
  url: string;
  success: boolean;
  status?: number;
  timing_ms: number;
  expected: string;
  actual: string;
  details?: Record<string, unknown>;
  error?: string;
}

export interface PageAudit {
  url: string;
  status: number;
  timing_ms: number;
  html_size_bytes: number;
  title: string;
  has_meta_description: boolean;
  has_viewport_meta: boolean;
  heading_count: number;
  link_count: number;
  image_count: number;
  images_without_alt: number;
  form_count: number;
  input_count: number;
  button_count: number;
  has_nav: boolean;
  has_footer: boolean;
  uses_semantic_html: boolean;
  color_contrast_issues: string[];
  text_content_preview: string;
  js_bundle_count: number;
  css_file_count: number;
  inline_style_count: number;
  aria_attributes: number;
  interactive_elements_without_labels: number;
}

export interface FeedbackReport {
  site_name: string;
  base_url: string;
  spec: string;
  generated_at: string;
  flow_results: StepResult[];
  page_audits: PageAudit[];
  browser_page_results?: BrowserPageResult[];
  browser_flow_results?: BrowserFlowResult[];
  scores: Record<string, { score: number; max: number; notes: string[] }>;
  overall_score: number;
  critical_issues: string[];
  improvements: string[];
  positive_aspects: string[];
  detailed_feedback: string;
}
