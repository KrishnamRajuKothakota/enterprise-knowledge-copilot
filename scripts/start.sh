#!/bin/bash
# Full stack startup script
# Usage: bash scripts/start.sh

set -e

echo "============================================"
echo "  Enterprise Knowledge Copilot — Starting"
echo "============================================"

# Check Ollama is reachable
OLLAMA_URL=${OLLAMA_BASE_URL:-http://172.16.29.1:11434}
echo "Checking Ollama at $OLLAMA_URL..."
if curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "  ✓ Ollama reachable"
else
    echo "  ✗ Ollama not reachable at $OLLAMA_URL"
    echo "    Start Ollama on host: systemctl start ollama"
    exit 1
fi

# Start infrastructure
echo "Starting PostgreSQL and Redis..."
docker compose up -d postgres redis

# Wait for postgres
echo "Waiting for PostgreSQL..."
until docker exec ekc_postgres pg_isready -U ekc_user -d ekc_db > /dev/null 2>&1; do
    sleep 1
done
echo "  ✓ PostgreSQL ready"

# Wait for redis
echo "Waiting for Redis..."
until docker exec ekc_redis redis-cli ping > /dev/null 2>&1; do
    sleep 1
done
echo "  ✓ Redis ready"

# Activate venv
source venv/bin/activate

# Warm up Ollama
echo "Warming up Ollama model..."
curl -s -X POST "$OLLAMA_URL/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3:8b","stream":false,"messages":[{"role":"user","content":"/no_think say ready"}]}' \
    > /dev/null 2>&1 && echo "  ✓ Ollama warmed" || echo "  ⚠ Ollama warmup failed (will retry on first query)"


# Start API
echo "Starting API server on port 8000..."
uvicorn src.ekc.main:app --host 0.0.0.0 --port 8000 --workers 1 &
API_PID=$!
echo "  ✓ API started (PID $API_PID)"

# Wait for API to be ready
sleep 5
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ API healthy"

# Warm response cache
echo "Warming response cache..."
python scripts/warm_cache.py > /dev/null 2>&1 && echo "  ✓ Cache warmed" || echo "  ⚠ Cache warmup failed (non-critical)"

# Start Streamlit
echo "Starting Streamlit UI on port 8501..."
streamlit run ui/streamlit_app/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true &
UI_PID=$!
echo "  ✓ Streamlit started (PID $UI_PID)"

echo ""
echo "============================================"
echo "  Enterprise Knowledge Copilot — Ready"
echo "============================================"
echo "  UI:  http://localhost:8501"
echo "  API: http://localhost:8000/docs"
echo ""
echo "  Demo accounts:"
echo "    admin@ekc.local    / admin123"
echo "    junior@ekc.local   / junior123"
echo "    l1@ekc.local       / l1support123"
echo "    lead@ekc.local     / lead123"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "============================================"

# Wait for interrupt
trap "echo 'Stopping...'; kill $API_PID $UI_PID 2>/dev/null; exit 0" INT TERM
wait
