# Enterprise Knowledge Copilot — Architecture

## Overview
Fully on-premise, multi-agent AI system for Indian IT services firms.
No queries or documents leave the enterprise network boundary.

## 7-Layer Architecture

### Layer 1 — Data Ingestion & Processing
- Multi-source connectors: PDF, CSV, PPTX, HTML, Markdown
- PII redaction: Microsoft Presidio + custom Aadhaar + PAN recognisers
- Heading-aware chunking: 512 tokens, 50-token overlap
- MinHash LSH near-duplicate detection (Jaccard threshold 0.85)
- Incremental sync: last_modified tracking

### Layer 2 — Knowledge Graph
- spaCy en_core_web_lg + custom IT-domain EntityRuler (43 patterns)
- Entity types: Technology, Project, Team, SOP, Ticket
- Alias resolution: "K8s" → tech:kubernetes
- NetworkX DiGraph + GraphML + PostgreSQL SQL mirror
- 19,797 nodes, 162,509 edges

### Layer 3 — Triple-Fusion Retrieval
- FAISS IndexFlatIP vector search (top-5)
- BM25Okapi keyword search (top-5)
- Entity-anchored 2-hop graph traversal (top-5)
- Reciprocal Rank Fusion (k=60)
- ms-marco-MiniLM-L-6-v2 cross-encoder reranking
- Redis response cache: TTL 24h, ~60% hit rate

### Layer 4 — Agentic Orchestration (LangGraph)
- SupervisorAgent: regex intent classification
- DocumentSearchAgent: cited SOP/doc retrieval
- TicketLookupAgent: similar resolved ticket search
- TicketAutoResolverAgent: ReAct loop, max 3 iterations, confidence ≥ 0.7
- EscalationAgent: pre-filled L2 Jira ticket when confidence < 0.7

### Layer 5 — LLM Response Generation
- Qwen3-8B 4-bit quantised via Ollama (fully on-premise)
- HallucinationGuard: regex grounding check + re-prompt on low confidence (weekly RAGAS batch for full evaluation)
- CitationEnforcer: every factual claim references a chunk_id
- Response schema: {answer, sources, confidence_score, follow_up_suggestions}

### Layer 6 — Self-Improving Feedback Loop
- Per-response thumbs-up/down ratings
- Nightly LLM-as-judge scoring batch job
- Weekly RAGAS evaluation on rolling sample

### Layer 7 — Evaluation & Observability
- RAGAS Faithfulness: 0.721 SOP domain / 0.565 full corpus (see evaluation_notes.md)
- Full audit log retained 12 months (DPDP Act compliance)
- Streamlit dashboard: RAGAS metrics, query volume, feedback

## Performance
| Metric | Value |
|--------|-------|
| Query latency (cached) | <200ms |
| Query latency (uncached, GPU) | ~3s |
| Query latency (uncached, P4000) | 12-15s |
| Cache hit rate | ~60% |
| FAISS search | <50ms |

## Security
- JWT + RBAC on all endpoints
- Document-level namespace isolation
- Pre-ingestion PII redaction — originals never stored
- TLS 1.3 via Nginx (production deployment)
- DPDP Act 2023 compliant
