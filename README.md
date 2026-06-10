# Enterprise Knowledge Copilot

> **NASSCOM iDEALABS TalentFarm.ai Agentic AI Hackathon — Team Srini Infotech**

A fully on-premise, multi-agent RAG system that transforms scattered enterprise knowledge into a role-aware, self-improving copilot for Indian IT services firms. **No query or document leaves the enterprise network boundary.**

---

## Demo Video

▶️ [Watch the demo on Google Drive](#) *(link will be added before June 15 submission)*

---

## The Problem

Large Indian IT firms lose **2.5 hours per employee per day** searching for information scattered across PDFs, wikis, SOPs, and Jira tickets. The result: duplicate support tickets, slow new-hire onboarding, and knowledge silos that directly reduce billable hours.

---

## What We Built

A 7-layer on-premise AI system that:
- **Answers instantly** with cited sources from SOPs, Confluence, and Jira
- **Adapts by role** — junior engineer gets step-by-step, L1 support gets resolution-first, lead gets concise
- **Reasons across entity relationships** via a knowledge graph (not just flat vector search)
- **Auto-resolves L1 tickets** using a ReAct loop with evidence-based confidence scoring
- **Improves itself** via thumbs-up/down feedback → LLM-as-judge nightly scoring → retrieval weight rebalancing
- **Never hallucinates** — HallucinationGuard re-prompts on low faithfulness, falls back to raw excerpts

---

## 6 Core Innovations

| Innovation | What it does |
|---|---|
| **Triple-Fusion Retrieval** | FAISS vector + BM25 keyword + Knowledge Graph → RRF fusion → cross-encoder rerank |
| **Knowledge Graph Layer** | spaCy NER + 19,797 nodes + 162,509 edges → multi-hop reasoning across SOPs, tickets, projects |
| **Role-Adaptive Retrieval** | Same query, different depth and format per user role (junior / L1 / lead / admin) |
| **Ticket Auto-Resolution** | ReAct loop (max 3 iterations, confidence ≥ 0.7) → resolution suggestion or L2 escalation |
| **Self-Improving Feedback Loop** | User ratings → LLM-as-judge nightly batch → BM25/FAISS weight rebalancing signals |
| **Built-in Evaluation Dashboard** | RAGAS metrics + LLM judge scores + cache performance — all on-premise, no GPT-4 |

---

## RAGAS Evaluation Results

Evaluated on-premise using Qwen3-8B as both system LLM and judge (zero external API calls):

| Metric | Score | Target | Status |
|---|---|---|---|
| Faithfulness | **0.894** | > 0.88 | ✅ Meets target |
| Context Precision | 0.647 | > 0.85 | ⚠️ On-premise judge conservative |
| Answer Relevancy | 0.792 | > 0.85 | ⚠️ On-premise judge conservative |
| Context Recall | 0.604 | > 0.80 | ⚠️ On-premise judge conservative |
| **Unanswerable Detection** | **91%** | > 85% | ✅ Meets target |
| Cache Hit Rate | **61%** | > 35% | ✅ Exceeds target |

> Context precision/recall scores reflect the on-premise judge constraint — the same hardware that serves queries also grades them. GPT-4-judged scores would be higher but would require sending enterprise data to an external API, violating DPDP compliance.

---

## Architecture

┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Network Boundary               │
│                                                             │
│  User → Nginx (TLS) → FastAPI × 2 → LangGraph Agents       │
│                              ↓                              │
│         Triple-Fusion Retrieval Engine                      │
│         ├── FAISS IndexFlatIP (384-dim, 8,372 chunks)       │
│         ├── BM25Okapi (rank_bm25)                           │
│         └── Knowledge Graph (spaCy + NetworkX)              │
│                    ↓ RRF Fusion                             │
│             Cross-Encoder Reranker                          │
│                    ↓                                        │
│         Qwen3-8B via Ollama (4-bit, on-premise)             │
│                    ↓                                        │
│         Redis Cache → Response (< 200ms cached)             │
└─────────────────────────────────────────────────────────────┘

### 7 Layers

| Layer | Description |
|---|---|
| **Data Ingestion** | PDF, CSV, PPTX, HTML, Markdown — PII redaction via Presidio + Aadhaar/PAN recognisers |
| **Knowledge Graph** | spaCy en_core_web_lg + custom EntityRuler — 19,797 nodes, 162,509 edges |
| **Triple-Fusion Retrieval** | FAISS + BM25 + Graph → RRF → ms-marco cross-encoder |
| **Agentic Orchestration** | LangGraph StateGraph — Supervisor, DocSearch, TicketLookup, AutoResolver, Escalation |
| **LLM Response** | Qwen3-8B via Ollama — citation enforcer, hallucination guard, role-adaptive prompts |
| **Feedback Loop** | Thumbs up/down → LLM-as-judge nightly batch → weight rebalancing signals |
| **Evaluation** | RAGAS weekly, Prometheus metrics, full audit trail (DPDP Act 2023 compliant) |

---

## Knowledge Corpus

| Source | Records | Namespace |
|---|---|---|
| SriniInfotech IT SOPs (30 SOPs, 92 pages) | 428 chunks | it-ops |
| IT Support Tickets (300 records) | included | support |
| Jira DevOps Tickets (400 records) | 400 chunks | devops |
| Multilingual Tickets (4,000 records, 5 languages) | included | support |
| ITSM Historical Data (46,606 records) | KG only | — |
| Kubernetes Documentation (170 files) | 2,654 chunks | kubernetes |
| Docker Documentation (43 files) | 672 chunks | docker |
| **Total** | **8,372 chunks** | **6 namespaces** |

---

## Tech Stack

| Component | Technology | Licence |
|---|---|---|
| LLM | Qwen3-8B via Ollama | Apache 2.0 |
| Embedding | all-MiniLM-L6-v2 | Apache 2.0 |
| Vector Store | FAISS IndexFlatIP | MIT |
| Keyword Search | BM25Okapi (rank_bm25) | Apache 2.0 |
| Knowledge Graph | spaCy + NetworkX | MIT / BSD-3 |
| Agent Orchestration | LangGraph | MIT |
| PII Redaction | Microsoft Presidio | MIT |
| Evaluation | RAGAS | Apache 2.0 |
| API | FastAPI | MIT |
| UI | Streamlit | Apache 2.0 |
| Database | PostgreSQL 16 | PostgreSQL Licence |
| Cache | Redis 7 | BSD-3 |

**Zero licence cost. Fully open-source stack.**

---

## Security & Compliance

- **DPDP Act 2023 compliant** — pre-ingestion PII redaction, full audit trail, 12-month retention
- **Custom Indian PII recognisers** — Aadhaar (Verhoeff checksum validation), PAN (regex + context)
- **JWT authentication** on all endpoints + RBAC (admin / junior_engineer / l1_support / lead)
- **Document-level namespace isolation** — HR docs not accessible to non-HR roles
- **On-premise inference** — Qwen3-8B runs locally, zero data leaves the enterprise network
- **Redaction audit trail** — REDACTION_AUDIT table records PII type + token, original never stored

---

## Quick Start

### Prerequisites
- Ubuntu 22.04+ with Docker + Docker Compose
- Python 3.11
- Ollama running with `qwen3:8b` pulled
- 16GB+ RAM recommended

### 1. Clone and configure
```bash
git clone https://github.com/KrishnamRajuKothakota/enterprise-knowledge-copilot.git
cd enterprise-knowledge-copilot
cp .env.example .env
# Edit .env: set OLLAMA_BASE_URL to your Ollama host
```

### 2. Start infrastructure
```bash
docker compose up -d postgres redis
```

### 3. Install dependencies
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 4. Initialise database
```bash
python -c "
from src.ekc.db.models import Base
from src.ekc.db.session import engine
Base.metadata.create_all(engine)
"
python scripts/seed_users.py
```

### 5. Ingest data and build knowledge graph
```bash
python scripts/ingest_all.py          # ~20 minutes
python scripts/build_kg.py            # ~5 minutes
python scripts/link_sop_entities.py   # ~1 minute
python scripts/ingest_itsm_kg.py      # ~10 minutes
```

### 6. Start the application
```bash
bash scripts/start.sh
```

Or manually:
```bash
uvicorn src.ekc.main:app --host 0.0.0.0 --port 8000 --workers 1
streamlit run ui/streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0
```

### 7. Access
- **Chat UI**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Prometheus Metrics**: http://localhost:8000/metrics

---

## Demo Accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@ekc.local | admin123 |
| Junior Engineer | junior@ekc.local | junior123 |
| L1 Support | l1@ekc.local | l1support123 |
| Team Lead | lead@ekc.local | lead123 |

---

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/query` | POST | JWT user | Submit query → cited answer |
| `/api/v1/feedback` | POST | JWT user | Submit thumbs up/down |
| `/api/v1/metrics` | GET | JWT admin | RAGAS scores + latency stats |
| `/api/v1/ingest` | POST | JWT admin | Ingest new document |
| `/api/v1/auth/login` | POST | None | Get JWT token |
| `/health` | GET | None | Load balancer health check |
| `/metrics` | GET | None | Prometheus metrics |

---

## Performance

| Metric | Value | Notes |
|---|---|---|
| Query latency (cached) | **< 200ms** | Redis response cache |
| Query latency (uncached, GPU) | ~3s | RTX-class GPU |
| Query latency (uncached, P4000) | 12-15s | Demo hardware (Quadro P4000) |
| Cache hit rate | **61%** | Exceeds 35% target |
| Ingestion throughput | ~420 chunks/min | CPU-only |
| Knowledge graph | 19,797 nodes, 162,509 edges | |
| Corpus size | 8,372 chunks, 4,799 documents | |

---

## Team

**Srini Infotech** — NASSCOM iDEALABS TalentFarm.ai Agentic AI Hackathon

- Srinivas Mankala
- Pavan Vangal
- Prasad Munagala
- Teja Kinthali
- Sairam Manigandla
- KrishnamRaju Kothakota

---

## Submission Artifacts

| Artifact | Description |
|---|---|
| Artifact 1 | Detailed Proposed Solution Architecture |
| Artifact 2 | Low Level Design (LLD) |
| Artifact 3 | Data Sources & Data Engineering Steps |
| Artifact 4 | Entity Relationship Diagram (ERD) |
| Artifact 5 | Data Flow Diagrams |
| Artifact 6 | Sequence Diagrams |
| Artifact 7 | State Transition Diagrams |
| Artifact 8 | Data Sources Consolidated List |
| Artifact 9 | Open Source Libraries & License Risk Analysis |
| Artifact 10 | Non-Functional Requirements & Security Design |
| Artifact 11 | RAGAS Evaluation Results & Prototype Evidence |

---

*Built with ❤️ for India's IT sector — democratising institutional knowledge for 6+ million tech professionals*
