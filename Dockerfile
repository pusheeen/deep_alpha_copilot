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
COPY fetch_data ./fetch_data
COPY target_tickers.py ./
COPY fetch_data.py ./
COPY storage_helper.py ./
COPY main.py ./
COPY bigquery_uploader.py ./
COPY bigquery_schemas.py ./
COPY email_notifier.py ./

# Create /tmp/data directory for Cloud Storage cache
RUN mkdir -p /tmp/data && ln -s /tmp/data /app/data

# Set environment variables
ENV DATA_ROOT=/tmp/data
ENV PYTHONUNBUFFERED=1

# Run the FastAPI application via Uvicorn
# Cloud Run injects the PORT environment variable
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT