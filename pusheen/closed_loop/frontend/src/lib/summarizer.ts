/**
 * AI summarization & anti-clickbait title generation.
 * Uses Gemini Flash via its OpenAI-compatible endpoint.
 */
import OpenAI from 'openai';
import { cacheGet, cacheSet, makeCacheKey } from './cache';
import { Article, extractArticleContent } from './news-fetcher';

let geminiClient: OpenAI | null = null;

function getGeminiClient(): OpenAI {
  if (!geminiClient) {
    geminiClient = new OpenAI({
      apiKey: process.env.GEMINI_API_KEY || '',
      baseURL:
        process.env.GEMINI_BASE_URL ||
        'https://generativelanguage.googleapis.com/v1beta/openai/',
    });
  }
  return geminiClient;
}

const SYSTEM_PROMPT = `You are a news analyst. Given an article's original title and content, produce:

1. **generated_title** — A concise, accurate, non-clickbait title that faithfully represents the article's actual content. Remove sensationalism, vague teasers, and emotional manipulation. Keep it informative.
2. **summary** — A TL;DR of 2-3 sentences capturing the key facts. No fluff.
3. **clickbait_score** — A float from 0.0 (not clickbait) to 1.0 (extreme clickbait) rating how clickbaity the ORIGINAL title is.
4. **is_clickbait** — Boolean, true if clickbait_score >= 0.6.

Respond ONLY with valid JSON matching this schema:
{
  "generated_title": "string",
  "summary": "string",
  "clickbait_score": 0.0,
  "is_clickbait": false
}`;

interface SummaryResult {
  generated_title: string;
  summary: string;
  clickbait_score: number;
  is_clickbait: boolean;
}

export async function summarizeArticle(
  originalTitle: string,
  content: string,
  url: string
): Promise<SummaryResult> {
  const cacheKey = makeCacheKey('summary', { url });
  const cached = cacheGet<SummaryResult>(cacheKey);
  if (cached) return cached;

  if (!process.env.GEMINI_API_KEY) {
    console.warn('GEMINI_API_KEY not set — skipping AI summarization');
    const clean = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    const result: SummaryResult = {
      generated_title: originalTitle,
      summary:
        clean.length > 200 ? clean.slice(0, 200) + '...' : clean || '',
      clickbait_score: 0,
      is_clickbait: false,
    };
    cacheSet(cacheKey, result, 3600000);
    return result;
  }

  const client = getGeminiClient();
  const model = process.env.GEMINI_MODEL || 'gemini-2.0-flash';

  try {
    const resp = await client.chat.completions.create({
      model,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        {
          role: 'user',
          content: `Original title: ${originalTitle}\n\nArticle content:\n${content.slice(0, 3000)}`,
        },
      ],
      temperature: 0.3,
      max_tokens: 500,
    });

    let raw = resp.choices[0]?.message?.content?.trim() || '';
    // Handle markdown code blocks
    if (raw.startsWith('```')) {
      raw = raw.split('\n').slice(1).join('\n').replace(/```$/, '').trim();
    }

    const result: SummaryResult = JSON.parse(raw);
    cacheSet(cacheKey, result, 3600000);
    return result;
  } catch (e) {
    console.error(`Summarization failed for "${url}":`, e);
    const clean = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    return {
      generated_title: originalTitle,
      summary:
        clean.length > 200 ? clean.slice(0, 200) + '...' : clean || '',
      clickbait_score: 0,
      is_clickbait: false,
    };
  }
}

export async function batchSummarize(
  articles: Article[]
): Promise<Article[]> {
  const BATCH_SIZE = 5;
  const enriched: Article[] = [];

  for (let i = 0; i < articles.length; i += BATCH_SIZE) {
    const batch = articles.slice(i, i + BATCH_SIZE);
    const results = await Promise.all(
      batch.map(async (article) => {
        let content = article.content_snippet || '';
        if (!content || content.length < 50) {
          content = await extractArticleContent(article.original_url);
          article.content_snippet = content;
        }

        const result = await summarizeArticle(
          article.original_title,
          content,
          article.original_url
        );

        return {
          ...article,
          generated_title: result.generated_title,
          summary: result.summary,
          clickbait_score: result.clickbait_score,
          is_clickbait: result.is_clickbait,
        };
      })
    );
    enriched.push(...results);
  }

  return enriched;
}
