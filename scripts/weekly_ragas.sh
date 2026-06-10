#!/bin/bash
# Weekly RAGAS evaluation + LLM judge batch
# Run via cron: 0 2 * * 0 bash /path/to/weekly_ragas.sh
set -e
cd ~/enterprise-knowledge-copilot
source venv/bin/activate

echo "$(date): Starting weekly RAGAS evaluation..."
python scripts/run_eval.py
echo "$(date): RAGAS complete"

echo "$(date): Running LLM judge batch..."
python scripts/llm_judge_batch.py --limit 100
echo "$(date): LLM judge complete"

echo "$(date): Weekly evaluation cycle complete"
