# Demo Script — Enterprise Knowledge Copilot

## Pre-Demo Checklist (30 min before)
- [ ] Host: confirm Ollama running — systemctl status ollama
- [ ] VM: start uvicorn — wait for "Ollama warmed up"
- [ ] VM: start Streamlit
- [ ] VM: python scripts/warm_cache.py — confirm all 10 under 1s
- [ ] Browser: http://localhost:8501, sign in as admin@ekc.local

## Demo Flow (10 minutes)

### 1. SOP Knowledge Retrieval (2 min)
Click: "What is the SLA for P1 incident resolution?"
Point out: cites SriniInfotech_SOPs_Volume1, section 4.2
Click follow-up: "What is the escalation path for P1 incidents?"

### 2. Role-Adaptive Responses (2 min)
Switch role to junior_engineer → ask "How do I escalate a VPN issue to L2?"
Switch to l1_support → ask same question
"Notice the answer format changes per role."

### 3. Knowledge Graph Multi-Hop (2 min)
Ask: "Which SOPs apply to auth-service that triggered JRA-1001?"
"This requires traversing: auth-service → Project Orion → SOP-IT-001
A flat vector search cannot answer this."

### 4. Honest Unanswerable Detection (1 min)
Ask: "Which SOPs cover CrashLoopBackOff?"
"It says I don't have enough information — correctly refuses to
hallucinate an SOP that doesn't exist."

### 5. RAGAS Dashboard (1 min)
Click Dashboard → show Faithfulness 0.894
"Evaluated on-premise with the same Qwen3-8B model. No GPT-4."

## Key Questions from Judges

Q: "Why 12-15 second latency?"
A: "First query on Quadro P4000 — on-premise constraint.
Cached queries <200ms. RTX GPU brings uncached to ~3s.
Documented honestly in Artifact 10."

Q: "RAGAS scores don't all meet targets?"
A: "Faithfulness exceeds target at 0.894. The other metrics
reflect the on-premise judge constraint — same hardware grades
and serves. GPT-4 judged numbers would be higher but wouldn't
reflect the actual deployment."

Q: "Is this actually on-premise?"
A: "Yes — Ollama on host, all data in PostgreSQL and FAISS on VM.
Nothing touches an external API."
