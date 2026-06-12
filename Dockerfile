FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_lg

# Copy application code
COPY src/ src/
COPY ui/ ui/
COPY scripts/ scripts/
COPY data/indexes/ data/indexes/
COPY data/eval/ data/eval/
# .env is NOT baked into image — mount via docker-compose env_file or environment

# Create necessary directories
RUN mkdir -p data/backups data/raw

EXPOSE 8000 8501

