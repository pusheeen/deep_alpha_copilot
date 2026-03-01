# Closed Loop — AI-Powered News Aggregator

A web app that aggregates news from multiple sources (Google News, email newsletters, Chrome bookmarks), generates anti-clickbait titles, and provides TL;DR summaries.

## Features

- **User Authentication** — Register/login with JWT-based auth
- **Google News Feed** — Fetches trending news via Google News RSS, filtered to the past 72 hours
- **Email Newsletter Import** — Paste newsletter HTML to extract and summarize articles
- **Chrome Bookmarks Import** — Upload your Chrome bookmarks export to process saved articles
- **AI Summarization** — Every article gets a TL;DR summary via OpenAI-compatible API
- **Anti-Clickbait Titles** — AI generates honest, descriptive titles based on actual content
- **Clickbait Detection** — Each article is scored 0-1 for clickbait, flagged articles are marked
- **Search** — Search across all your news by topic/keyword
- **Fast Loading** — In-memory caching (15 min for news, 1 hour for summaries)

## Tech Stack

- **Frontend**: Next.js 14 (App Router), React, Tailwind CSS
- **Backend**: Next.js API Routes (serverless-ready)
- **Database**: SQLite via better-sqlite3 (file-based, zero config)
- **AI**: OpenAI-compatible API (GPT-4o-mini default)
- **Deployment**: Vercel-ready

## Quick Start

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with your API keys

npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `JWT_SECRET` | Secret key for JWT token signing | Yes |
| `OPENAI_API_KEY` | OpenAI API key for summarization | No (fallback to truncated content) |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint | No |
| `SUMMARIZATION_MODEL` | Model to use (default: `gpt-4o-mini`) | No |
| `NEWS_FRESHNESS_HOURS` | Max article age in hours (default: `72`) | No |
| `CACHE_TTL_SECONDS` | News cache TTL in seconds (default: `900`) | No |

## API Routes

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login and get JWT |
| GET | `/api/auth/me` | Get current user |
| GET | `/api/news/feed` | Fetch and summarize news feed |
| GET | `/api/news/article` | Get single article details |
| POST | `/api/sources/add` | Add an RSS source |
| GET | `/api/sources/list` | List user's sources |
| DELETE | `/api/sources/add?id=X` | Remove a source |
| POST | `/api/sources/email` | Import email newsletter |
| POST | `/api/sources/bookmarks` | Import Chrome bookmarks |

## Project Structure

```
closed_loop/
├── backend/               # Python FastAPI backend (reference/alternative)
│   ├── core/              # Config, DB, security, cache
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # API endpoints
│   └── services/          # Business logic
└── frontend/              # Next.js app (primary)
    ├── src/
    │   ├── app/           # Pages and API routes
    │   ├── components/    # React components
    │   ├── context/       # Auth context
    │   ├── hooks/         # Custom hooks
    │   └── lib/           # Utilities (auth, db, cache, news, summarizer)
    └── vercel.json        # Vercel deployment config
```
