export interface SiteConfig {
  site_name: string;
  base_url: string;
  spec: string;
  flows: Flow[];
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
  scores: Record<string, { score: number; max: number; notes: string[] }>;
  overall_score: number;
  critical_issues: string[];
  improvements: string[];
  positive_aspects: string[];
  detailed_feedback: string;
}
