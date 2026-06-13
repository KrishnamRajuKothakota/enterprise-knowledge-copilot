"""
Enterprise Knowledge Copilot — Streamlit UI
Main chat interface with role selection, feedback, and cited sources.
"""
import streamlit as st
import httpx
import json

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="Enterprise Knowledge Copilot",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1F3A5F 0%, #2E5A8E 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        color: white !important;
    }
    .main-header h2 {
        color: white !important;
        font-weight: 700;
    }
    .main-header p {
        color: #CBD5E0 !important;
    }
    .source-card {
        background: #F8F9FA;
        border-left: 4px solid #C9A227;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    .confidence-high  { color: #28a745; font-weight: bold; }
    .confidence-med   { color: #ffc107; font-weight: bold; }
    .confidence-low   { color: #dc3545; font-weight: bold; }
    .metric-box {
        background: #1F3A5F;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .stButton > button {
        background: #1F3A5F;
        color: white;
        border: none;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
def init_session():
    defaults = {
        "token": None, "user_role": None, "user_email": None,
        "session_id": None, "messages": [], "last_query_id": None,
        "feedback_given": set(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ── Auth helpers ──────────────────────────────────────────────────────────────
def login(email: str, password: str) -> bool:
    try:
        r = httpx.post(f"{API_BASE}/auth/login",
                       json={"email": email, "password": password}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            st.session_state.token = data["access_token"]
            st.session_state.user_role = data["role"]
            st.session_state.user_email = email
            return True
    except Exception:
        pass
    return False


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def query_api(query: str) -> dict | None:
    try:
        payload = {"query": query}
        if st.session_state.session_id:
            payload["session_id"] = st.session_state.session_id
        # Send current role for role-adaptive responses
        if st.session_state.get("user_role"):
            payload["role"] = st.session_state.user_role
        r = httpx.post(f"{API_BASE}/query", json=payload,
                       headers=auth_headers(), timeout=120)
        if r.status_code == 200:
            return r.json()
    except httpx.TimeoutException:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}
    return None


def submit_feedback(query_id: str, rating: str):
    try:
        httpx.post(f"{API_BASE}/feedback",
                   json={"query_id": query_id,
                         "session_id": st.session_state.session_id or "",
                         "rating": rating},
                   headers=auth_headers(), timeout=10)
    except Exception:
        pass


# ── Login screen ──────────────────────────────────────────────────────────────
if not st.session_state.token:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class='main-header'>
            <h2>🧠 Enterprise Knowledge Copilot</h2>
            <p>Multi-agent RAG system with triple-fusion retrieval</p>
            <p><small>NASSCOM Agentic AI Hackathon — Team Srini Infotech</small></p>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Sign In")
        email = st.text_input("Email", placeholder="admin@ekc.local")
        password = st.text_input("Password", type="password")

        if st.button("Sign In", use_container_width=True):
            if login(email, password):
                st.success(f"Welcome! Role: {st.session_state.user_role}")
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.markdown("---")
        st.markdown("**Demo accounts:**")
        st.code("""admin@ekc.local     / admin123
junior@ekc.local    / junior123
l1@ekc.local        / l1support123
lead@ekc.local      / lead123""")
    st.stop()


# ── Main app ──────────────────────────────────────────────────────────────────
# Header
st.markdown(f"""
<div class='main-header'>
    <h2>🧠 Enterprise Knowledge Copilot</h2>
    <p>Triple-fusion RAG · LangGraph Agents · Knowledge Graph · DPDP Compliant</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown(f"**👤 {st.session_state.user_email}**")
    st.markdown(f"Role: `{st.session_state.user_role}`")
    st.markdown("---")

    # Role switcher (demo purposes)
    st.markdown("**🎭 Demo Role Switch**")
    demo_role = st.selectbox(
        "Switch role to see adaptive responses:",
        ["admin", "junior_engineer", "l1_support", "lead"],
        index=["admin", "junior_engineer", "l1_support", "lead"].index(
            st.session_state.user_role
        ) if st.session_state.user_role in
            ["admin", "junior_engineer", "l1_support", "lead"] else 0,
    )
    if demo_role != st.session_state.user_role:
        st.session_state.user_role = demo_role
        st.success(f"Role switched to: {demo_role}")
        st.rerun()

    st.markdown("---")
    st.markdown("**📊 Quick Metrics**")
    try:
        r = httpx.get(f"{API_BASE}/metrics", headers=auth_headers(), timeout=5)
        if r.status_code == 200:
            m = r.json()
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Queries (7d)", m["queries"]["total_7d"])
                st.metric("Chunks", m["corpus"]["total_chunks"])
            with col_b:
                st.metric("Avg Latency", f"{m['queries']['avg_latency_ms']}ms")
                st.metric("Cache Rate",
                          f"{m['queries']['cache_hit_rate']*100:.0f}%")
    except Exception:
        st.caption("Metrics unavailable")

    st.markdown("---")
    st.markdown("**💡 Sample Queries**")
    def set_pending_query(query: str):
        st.session_state["pending_query"] = query

    sample_queries = [
        "What is the SLA for P1 incident resolution?",
        "How do I escalate a VPN issue to L2?",
        "Find K8s rollback procedure",
        "New employee IT onboarding steps",
        "Which SOPs cover CrashLoopBackOff?",
        "What is the leaver account disable procedure?",
    ]
    for sq in sample_queries:
        st.button(sq, key=f"sample_{sq[:20]}", use_container_width=True, on_click=set_pending_query, args=(sq,))

    st.markdown("---")
    if st.button("🚪 Sign Out"):
        for k in ["token", "user_role", "user_email",
                  "session_id", "messages", "last_query_id"]:
            st.session_state[k] = None if k != "messages" else []
        st.session_state.feedback_given = set()
        st.rerun()

# ── Chat area ─────────────────────────────────────────────────────────────────
# chat_input must be outside columns to pin to page bottom
user_input = st.chat_input("Ask anything about your IT knowledge base...")

col_chat, col_info = st.columns([3, 1])

with col_chat:
    st.subheader("💬 Chat")

    # Show welcome when no messages
    if not st.session_state.messages:
        st.markdown("""
        <div style='text-align:center; padding: 60px 20px;'>
            <div style='font-size: 48px;'>🧠</div>
            <h3 style='color: inherit;'>Ask anything about your IT knowledge base</h3>
            <p style='color: inherit; opacity: 0.6;'>Try a sample query from the sidebar, or type your question below.</p>
        </div>
        """, unsafe_allow_html=True)

    # Display message history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["content"])

                # Sources
                if msg.get("sources"):
                    with st.expander(f"📚 {len(msg['sources'])} source(s)"):
                        for src in msg["sources"]:
                            st.markdown(f"""<div class='source-card'>
                            📄 <b>{src['doc_title'][:50]}</b><br>
                            📌 {src['section_title'][:60]}<br>
                            🏷️ namespace: {src['namespace']}
                            </div>""", unsafe_allow_html=True)

                # Confidence
                conf = msg.get("confidence_score", 0)
                conf_class = ("confidence-high" if conf > 0.7
                              else "confidence-med" if conf > 0.4
                              else "confidence-low")
                st.markdown(
                    f"<span class='{conf_class}'>Confidence: {conf:.0%}</span> "
                    f"{'⚡ cached' if msg.get('cache_hit') else ''}"
                    f"{'🔺 escalated' if msg.get('escalated') else ('⚠️ fallback' if msg.get('fallback') else '')}",
                    unsafe_allow_html=True,
                )

                # Follow-ups
                if msg.get("follow_ups"):
                    st.caption("💡 Follow-up suggestions:")
                    for fu in msg["follow_ups"]:
                        st.button(fu, key=f"fu_{hash(fu)}_{msg.get('query_id','')}", on_click=set_pending_query, args=(fu,))

                # Feedback buttons
                qid = msg.get("query_id")
                if qid and qid not in st.session_state.feedback_given:
                    fb_col1, fb_col2, fb_col3 = st.columns([1, 1, 8])
                    with fb_col1:
                        if st.button("👍", key=f"up_{qid}"):
                            submit_feedback(qid, "up")
                            st.session_state.feedback_given.add(qid)
                            st.rerun()
                    with fb_col2:
                        if st.button("👎", key=f"dn_{qid}"):
                            submit_feedback(qid, "down")
                            st.session_state.feedback_given.add(qid)
                            st.rerun()
                elif qid in st.session_state.feedback_given:
                    st.caption("✅ Feedback recorded")

    # Handle pending query from buttons
    pending = st.session_state.get("pending_query", None)
    if pending:
        del st.session_state["pending_query"]
    query_to_run = pending or user_input

    if query_to_run:
        st.session_state.messages.append({"role": "user", "content": query_to_run})

        with st.chat_message("user"):
            st.write(query_to_run)

        with st.chat_message("assistant"):
            with st.spinner("🔍 Running triple-fusion retrieval + LLM generation (~10-15s first query, instant if cached)..."):
                result = query_api(query_to_run)

            if result is None or "error" in result:
                error_msg = result.get("error", "unknown") if result else "API error"
                if error_msg == "timeout":
                    st.error("⏱️ Query timed out. The LLM is warming up — try again in 30 seconds.")
                else:
                    st.error(f"Error: {error_msg}")
            else:
                # Update session_id
                st.session_state.session_id = result.get("session_id")

                answer = result.get("answer", "No answer returned.")
                st.write(answer)

                # Sources expander
                sources = result.get("sources", [])
                if sources:
                    with st.expander(f"📚 {len(sources)} source(s)"):
                        for src in sources:
                            st.markdown(f"""<div class='source-card'>
                            📄 <b>{src['doc_title'][:50]}</b><br>
                            📌 {src['section_title'][:60]}<br>
                            🏷️ namespace: {src['namespace']}
                            </div>""", unsafe_allow_html=True)

                # Confidence + cache indicator
                conf = result.get("confidence_score", 0)
                conf_class = ("confidence-high" if conf > 0.7
                              else "confidence-med" if conf > 0.4
                              else "confidence-low")
                st.markdown(
                    f"<span class='{conf_class}'>Confidence: {conf:.0%}</span> "
                    f"{'⚡ cached' if result.get('cache_hit') else ''}"
                    f"{'🔺 escalated' if result.get('escalated') else ('⚠️ fallback' if result.get('fallback') else '')}",
                    unsafe_allow_html=True,
                )

                # Follow-up suggestions
                follow_ups = result.get("follow_up_suggestions", [])
                if follow_ups:
                    st.caption("💡 You might also ask:")
                    for fu in follow_ups:
                        st.button(fu, key=f"fu_new_{hash(fu)}", on_click=set_pending_query, args=(fu,))

                # Save to history
                st.session_state.last_query_id = result.get("query_id")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "confidence_score": conf,
                    "cache_hit": result.get("cache_hit", False),
                    "fallback": result.get("fallback", False),
                    "follow_ups": follow_ups,
                    "query_id": result.get("query_id"),
                })

                # Feedback buttons for latest message
                qid = result.get("query_id")
                if qid:
                    st.caption("Was this helpful?")
                    fb1, fb2, fb3 = st.columns([1, 1, 8])
                    with fb1:
                        if st.button("👍", key=f"up_new_{qid}"):
                            submit_feedback(qid, "up")
                            st.session_state.feedback_given.add(qid)
                            st.rerun()
                    with fb2:
                        if st.button("👎", key=f"dn_new_{qid}"):
                            submit_feedback(qid, "down")
                            st.session_state.feedback_given.add(qid)
                            st.rerun()

with col_info:
    st.subheader("🏗️ Architecture")
    st.markdown("""
    **Retrieval:**
    - 🔢 Vector (FAISS)
    - 🔤 BM25 keyword
    - 🕸️ Knowledge Graph
    - ⚡ RRF Fusion
    - 🎯 Cross-encoder rerank

    **Agents:**
    - 🎛️ Supervisor
    - 📄 Doc Search
    - 🎫 Ticket Lookup
    - 🤖 Auto Resolver

    **Security:**
    - 🔐 JWT + RBAC
    - 🛡️ PII Redaction
    - 🏷️ Aadhaar + PAN
    - 📋 Audit Trail

    **Corpus:**
    """)
    try:
        r = httpx.get(f"{API_BASE}/metrics", headers=auth_headers(), timeout=5)
        if r.status_code == 200:
            m = r.json()
            st.markdown(f"""
    - 📚 {m['corpus']['total_documents']} documents
    - 🧩 {m['corpus']['total_chunks']} chunks
    - 🌐 K8s + Docker + SOPs
            """)
    except Exception:
        st.markdown("- 📚 8,372 chunks")