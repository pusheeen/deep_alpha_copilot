/**
 * HTTP fetcher with timing, retries, and response capture.
 */

export interface FetchResult {
  status: number;
  ok: boolean;
  timing_ms: number;
  headers: Record<string, string>;
  body: string;
  json: unknown | null;
  error?: string;
}

export async function timedFetch(
  url: string,
  options: RequestInit = {},
  timeoutMs = 30000
): Promise<FetchResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const start = Date.now();

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'User-Agent': 'UserAgentSimulator/1.0',
        ...(options.headers || {}),
      },
    });
    const body = await res.text();
    const timing_ms = Date.now() - start;

    const headers: Record<string, string> = {};
    res.headers.forEach((v, k) => { headers[k] = v; });

    let json: unknown | null = null;
    try { json = JSON.parse(body); } catch { /* not json */ }

    return { status: res.status, ok: res.ok, timing_ms, headers, body, json };
  } catch (e) {
    return {
      status: 0,
      ok: false,
      timing_ms: Date.now() - start,
      headers: {},
      body: '',
      json: null,
      error: e instanceof Error ? e.message : String(e),
    };
  } finally {
    clearTimeout(timer);
  }
}
