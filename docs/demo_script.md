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

## Scenario 6 — Self-Improving Feedback Loop (NEW)

**Narrative:** Show the system has learned from user feedback.

**Step 1** — Open Dashboard → Weight Signals panel. Show k8s_docker: BM25=0.6, Vector=0.4.
Say: "After users rated K8s responses poorly, the system detected this pattern overnight
and rebalanced retrieval — giving more weight to keyword search for technical commands."

**Step 2** — Show the LLM judge scores table. Point out the thumbs-down K8s entries
scored low (0.0, 0.4) which triggered the rebalancing.

**Script:** "This is the self-improving feedback loop in action. Five K8s thumbs-down
ratings, one overnight judge batch, and the retrieval weights automatically adjusted.
No manual tuning, no retraining — the system learned from usage."

---

## Scenario 7 — Organic Knowledge Graph Multi-Hop (NEW)

**Query:** "What procedures cover VPN access issues on Lenovo devices?"

**What to say:** "This query doesn't mention any SOP by name. The knowledge graph
traverses: Lenovo device → related to → sop:vpn_access → retrieves SOP chunks.
The connection between a hardware brand and an IT procedure only exists in the
graph — not in any single document. This is multi-hop reasoning, not keyword search."

**Expected:** Answer citing SriniInfotech SOPs Volume 1, confidence ~60%.

**Note:** Cisco router query correctly refuses — demonstrates honest knowledge boundaries.

---

## Scenario 8 — Unanswerable Detection

**Query:** "What is the WiFi password for the Mumbai office?"

**Expected:** "I don't have enough information" — confidence ~10%.

**What to say:** "The system refuses to hallucinate. It retrieves, finds no grounded
answer, and says so. 91% refusal rate on 22 adversarial out-of-scope queries."

---

## Pre-Demo Checklist

- [ ] bash scripts/start.sh (starts everything)
- [ ] python scripts/warm_cache.py (all queries <200ms)
- [ ] Confirm health: curl -sk https://localhost/health
- [ ] Open Streamlit at http://localhost:8501
- [ ] Login as admin@ekc.local
- [ ] Open Dashboard tab — verify RAGAS scores and weight signals show
- [ ] Switch to junior@ekc.local — show role-adaptive response difference
- [ ] Have all 8 query strings ready to paste
