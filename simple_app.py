#!/usr/bin/env python3
"""
Simple FastAPI app for Financial Agent - Reddit data only
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
import glob
from pathlib import Path
from target_tickers import TARGET_TICKERS

app = FastAPI(title="Financial Agent - Reddit Analytics", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    status: str

def load_reddit_data():
    """Load Reddit sentiment data"""
    data_dir = Path("data/unstructured/reddit")
    reddit_files = list(data_dir.glob("reddit_posts_*.json"))
    summary_files = list(data_dir.glob("reddit_summary_*.json"))

    if not reddit_files:
        return {"posts": [], "summaries": {}}

    # Load latest posts file
    latest_posts_file = max(reddit_files, key=lambda x: x.stat().st_mtime)
    with open(latest_posts_file, 'r') as f:
        posts = json.load(f)

    # Load latest summary file
    summaries = {}
    if summary_files:
        latest_summary_file = max(summary_files, key=lambda x: x.stat().st_mtime)
        with open(latest_summary_file, 'r') as f:
            summaries = json.load(f)

    return {"posts": posts, "summaries": summaries}

def analyze_ticker_sentiment(ticker: str, reddit_data: dict):
    """Analyze sentiment for a specific ticker"""
    summaries = reddit_data.get("summaries", {})
    posts = reddit_data.get("posts", [])

    if ticker.upper() not in summaries:
        return f"No Reddit sentiment data found for {ticker.upper()}."

    ticker_summary = summaries[ticker.upper()]
    total = ticker_summary.get("total_posts", 0)
    bullish = ticker_summary.get("bullish_posts", 0)
    bearish = ticker_summary.get("bearish_posts", 0)
    neutral = ticker_summary.get("neutral_posts", 0)
    subreddits = ticker_summary.get("subreddits", [])

    # Calculate percentages
    if total > 0:
        bullish_pct = (bullish / total) * 100
        bearish_pct = (bearish / total) * 100
        neutral_pct = (neutral / total) * 100
    else:
        bullish_pct = bearish_pct = neutral_pct = 0

    # Get recent posts for context
    ticker_posts = [p for p in posts if ticker.upper() in p.get("mentioned_tickers", [])]
    recent_posts = sorted(ticker_posts, key=lambda x: x.get("created_utc", 0), reverse=True)[:3]

    response = f"""**Reddit Sentiment Analysis for {ticker.upper()}:**

📊 **Overall Statistics:**
- Total Posts: {total}
- Bullish: {bullish} ({bullish_pct:.1f}%)
- Bearish: {bearish} ({bearish_pct:.1f}%)
- Neutral: {neutral} ({neutral_pct:.1f}%)

📍 **Active Subreddits:** {', '.join(subreddits)}

🔥 **Recent Discussions:**"""

    for i, post in enumerate(recent_posts[:2], 1):
        title = post.get("title", "")[:60]
        sentiment = post.get("sentiment", "neutral")
        subreddit = post.get("subreddit", "unknown")
        response += f"\n{i}. r/{subreddit}: \"{title}...\" ({sentiment})"

    return response

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Serve the chat frontend"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Financial Agent - Reddit Analytics</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 flex flex-col items-center justify-center h-screen">
    <div class="w-full max-w-2xl h-full md:h-5/6 flex flex-col bg-white shadow-2xl rounded-lg">
        <div class="p-4 border-b bg-blue-600 text-white rounded-t-lg">
            <h1 class="text-2xl font-bold text-center">Financial Agent - Reddit Analytics</h1>
            <p class="text-sm text-center text-blue-100">Ask about Reddit sentiment for stocks like NVDA, IREN, NXE, etc.</p>
        </div>

        <div id="chat-container" class="flex-1 p-6 overflow-y-auto">
            <div class="flex justify-start mb-4">
                <div class="bg-gray-200 text-gray-800 p-3 rounded-lg max-w-md">
                    <p>Hello! I can analyze Reddit sentiment for stocks. Try asking: "What's the Reddit sentiment for NVDA?" or "Show me IREN discussion trends"</p>
                </div>
            </div>
        </div>

        <div class="p-4 border-t bg-gray-50 rounded-b-lg">
            <form id="chat-form" class="flex items-center space-x-3">
                <input type="text" id="user-input" placeholder="Ask about Reddit sentiment..." class="flex-1 p-3 border rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 transition">
                <button type="submit" class="bg-blue-600 text-white p-3 rounded-full hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition duration-300 transform hover:scale-105">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                </button>
            </form>
        </div>
    </div>

    <script>
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');
        const chatContainer = document.getElementById('chat-container');
        const apiUrl = '/chat';

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const question = userInput.value.trim();
            if (!question) return;

            addMessage(question, 'user');
            userInput.value = '';

            const typingIndicator = addMessage('Analyzing Reddit data...', 'bot', true);

            try {
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: question })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                typingIndicator.remove();
                addMessage(data.answer, 'bot');

            } catch (error) {
                console.error('Error:', error);
                typingIndicator.remove();
                addMessage('Sorry, there was an error processing your request.', 'bot');
            }
        });

        function addMessage(text, sender, isTyping = false) {
            const messageWrapper = document.createElement('div');
            messageWrapper.className = `flex mb-4 ${sender === 'user' ? 'justify-end' : 'justify-start'}`;

            const messageBubble = document.createElement('div');
            messageBubble.className = `p-3 rounded-lg max-w-md ${sender === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'}`;

            if (isTyping) {
                messageBubble.innerHTML = '<div class="animate-pulse">Analyzing...</div>';
                messageWrapper.id = "typing-indicator";
            } else {
                messageBubble.innerHTML = text.replace(/\\n/g, '<br>').replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
            }

            messageWrapper.appendChild(messageBubble);
            chatContainer.appendChild(messageWrapper);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return messageWrapper;
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests"""
    question = request.question.lower()

    # Load Reddit data
    reddit_data = load_reddit_data()

    # Use tickers from central config
    detected_ticker = None
    for ticker in TARGET_TICKERS:
        if ticker.lower() in question:
            detected_ticker = ticker
            break

    if detected_ticker:
        answer = analyze_ticker_sentiment(detected_ticker, reddit_data)
    elif "reddit" in question or "sentiment" in question:
        # General Reddit overview
        summaries = reddit_data.get("summaries", {})
        total_posts = sum(s.get("total_posts", 0) for s in summaries.values())
        answer = f"""**Reddit Financial Sentiment Overview:**

📊 **Data Collected:** {total_posts} posts across {len(summaries)} tickers

🔥 **Most Discussed Tickers:**"""

        # Sort by total posts
        sorted_tickers = sorted(summaries.items(), key=lambda x: x[1].get("total_posts", 0), reverse=True)
        for ticker, data in sorted_tickers[:5]:
            posts = data.get("total_posts", 0)
            bullish = data.get("bullish_posts", 0)
            bearish = data.get("bearish_posts", 0)
            sentiment = "📈 Bullish" if bullish > bearish else "📉 Bearish" if bearish > bullish else "➡️ Neutral"
            answer += f"\n• {ticker}: {posts} posts ({sentiment})"

        answer += "\n\nAsk about a specific ticker for detailed analysis!"
    else:
        answer = """I can analyze Reddit sentiment for financial stocks!

Try asking:
• "What's the Reddit sentiment for NVDA?"
• "Show me IREN discussion trends"
• "Reddit sentiment overview"

Available tickers: """ + ", ".join(TARGET_TICKERS)

    return ChatResponse(answer=answer, status="success")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "reddit-analytics"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)