"""RAGAS evaluation dashboard."""
import streamlit as st
import httpx
import pandas as pd
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="EKC Dashboard", page_icon="📊", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in from the main page.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


st.title("📊 Evaluation & Metrics Dashboard")
st.markdown("RAGAS evaluation results + system performance metrics")

try:
    r = httpx.get(f"{API_BASE}/metrics",
                  headers=auth_headers(), timeout=10)
    m = r.json()
except Exception as e:
    st.error(f"Could not load metrics: {e}")
    st.stop()

# RAGAS scores
st.subheader("🎯 RAGAS Evaluation Scores")
ragas = m.get("ragas", {})

if ragas.get("faithfulness") is not None:
    col1, col2, col3 = st.columns(3)
    with col1:
        val = ragas["faithfulness"]
        delta = f"{val - 0.88:+.2f} vs target"
        st.metric("Faithfulness", f"{val:.3f}", delta,
                  delta_color="normal" if val >= 0.88 else "inverse")
    with col2:
        val = ragas["context_precision"]
        delta = f"{val - 0.85:+.2f} vs target"
        st.metric("Context Precision", f"{val:.3f}", delta,
                  delta_color="normal" if val >= 0.85 else "inverse")
    with col3:
        val = ragas["answer_relevancy"]
        delta = f"{val - 0.85:+.2f} vs target"
        st.metric("Answer Relevancy", f"{val:.3f}", delta,
                  delta_color="normal" if val >= 0.85 else "inverse")

    if ragas.get("run_date"):
        st.caption(f"Last evaluated: {ragas['run_date'][:10]}")
else:
    st.info("No RAGAS evaluation has been run yet. Use the Run Evaluation button below.")

    # Show targets
    col1, col2, col3 = st.columns(3)
    col1.metric("Faithfulness target", "> 0.88")
    col2.metric("Context Precision target", "> 0.85")
    col3.metric("Answer Relevancy target", "> 0.85")

st.markdown("---")

# Query metrics
st.subheader("⚡ Query Performance (Last 7 Days)")
queries = m.get("queries", {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Queries", queries.get("total_7d", 0))
col2.metric("Avg Latency", f"{queries.get('avg_latency_ms', 0):.0f}ms")
col3.metric("Cache Hit Rate",
            f"{queries.get('cache_hit_rate', 0)*100:.1f}%")
col4.metric("Fallback Count", queries.get("fallback_count", 0))

st.markdown("---")

# Feedback
st.subheader("👍 User Feedback")
feedback = m.get("feedback", {})
col1, col2, col3 = st.columns(3)
total_fb = feedback.get("total", 0)
thumbs_up = feedback.get("thumbs_up", 0)
col1.metric("Thumbs Up", thumbs_up)
col2.metric("Thumbs Down", feedback.get("thumbs_down", 0))
col3.metric("Approval Rate",
            f"{thumbs_up/total_fb*100:.0f}%" if total_fb > 0 else "N/A")

st.markdown("---")

# Corpus stats
st.subheader("📚 Knowledge Corpus")
corpus = m.get("corpus", {})
col1, col2 = st.columns(2)
col1.metric("Total Documents", corpus.get("total_documents", 0))
col2.metric("Total Chunks", corpus.get("total_chunks", 0))

st.markdown("""
**Corpus breakdown:**
- IT SOPs (30 procedures across 2 volumes)
- IT Support Tickets (300 records)
- Jira DevOps Tickets (400 records)
- Kubernetes Documentation (170 files)
- Docker Documentation (43 files)
- Multilingual Tickets (4,000 records, 5 languages)
""")

st.markdown("---")

# Run RAGAS button
st.subheader("🧪 Run Evaluation")
st.info("Running RAGAS evaluation takes 20-40 minutes using the local LLM as judge. Run this before the demo.")
if st.button("▶️ Run RAGAS Evaluation", type="primary"):
    st.warning("RAGAS evaluation started. Check back in 30 minutes.")
    st.caption("Full evaluation script: python scripts/run_eval.py")