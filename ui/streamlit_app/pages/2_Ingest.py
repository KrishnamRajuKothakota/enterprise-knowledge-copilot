"""Document ingestion admin page."""
import streamlit as st
import httpx
import os

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="EKC Ingest", page_icon="📥", layout="wide")

if not st.session_state.get("token"):
    st.warning("Please sign in from the main page.")
    st.stop()

if st.session_state.get("user_role") != "admin":
    st.error("Admin role required for ingestion.")
    st.stop()


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


st.title("📥 Document Ingestion Admin")
st.markdown("Ingest new documents into the knowledge base.")

st.subheader("Ingest a file")

col1, col2 = st.columns(2)
with col1:
    file_path = st.text_input(
        "File path (on server)",
        placeholder="/home/nasscomhackathon/enterprise-knowledge-copilot/data/raw/your_file.pdf"
    )
    namespace = st.selectbox(
        "Namespace",
        ["general", "it-ops", "support", "devops",
         "kubernetes", "docker", "hr", "finance"],
    )

with col2:
    access_roles = st.multiselect(
        "Access roles",
        ["admin", "junior_engineer", "l1_support", "lead"],
        default=["admin", "junior_engineer", "l1_support", "lead"],
    )

if st.button("🚀 Ingest Document", type="primary"):
    if not file_path:
        st.error("Please provide a file path.")
    else:
        with st.spinner("Ingesting... this may take a minute."):
            try:
                r = httpx.post(
                    f"{API_BASE}/ingest",
                    json={
                        "file_path": file_path,
                        "namespace": namespace,
                        "access_roles": access_roles,
                    },
                    headers=auth_headers(),
                    timeout=300,
                )
                if r.status_code == 202:
                    result = r.json()
                    st.success(
                        f"✅ Ingestion complete: "
                        f"{result['chunks_created']} chunks, "
                        f"{result['embeddings_created']} embeddings, "
                        f"{result['pii_redactions']} PII redactions"
                    )
                else:
                    st.error(f"Error {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"Ingestion failed: {e}")

st.markdown("---")
st.subheader("📁 Available files in data/raw/")

data_dir = "/home/nasscomhackathon/enterprise-knowledge-copilot/data/raw"
try:
    files = []
    for f in os.listdir(data_dir):
        full = os.path.join(data_dir, f)
        if os.path.isfile(full):
            size_mb = os.path.getsize(full) / 1024 / 1024
            files.append({"File": f, "Size (MB)": f"{size_mb:.1f}"})
    if files:
        st.dataframe(files, use_container_width=True)
except Exception:
    st.caption("Could not list files.")