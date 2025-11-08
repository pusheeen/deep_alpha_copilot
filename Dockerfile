FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY target_tickers.py ./
COPY fetch_data.py ./
COPY storage_helper.py ./
COPY main.py ./
COPY bigquery_uploader.py ./
COPY bigquery_schemas.py ./
COPY email_notifier.py ./
# NOTE: Do NOT copy data/ folder - it will be downloaded from Cloud Storage

# Create /tmp/data directory for Cloud Storage cache
RUN mkdir -p /tmp/data

# Set environment variables
ENV PORT=8080
ENV DATA_ROOT=/tmp/data
ENV PYTHONUNBUFFERED=1

# Run the Flask application (for Cloud Run with /fetch endpoint)
# For local FastAPI development, use: uvicorn app.main:app --reload
CMD ["python", "main.py"]
