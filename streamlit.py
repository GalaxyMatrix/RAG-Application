import asyncio
from pathlib import Path
import time
import httpx

import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

# Page config with custom theme
st.set_page_config(
    page_title="RAG AI Study Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling with improved visibility
st.markdown("""
    <style>
    .main {
        padding: 2rem;
        background-color: #ffffff;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: 600;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .upload-text {
        font-size: 1.2rem;
        font-weight: 600;
        color: #2c3e50;
    }
    .success-box {
        padding: 1.5rem;
        border-radius: 12px;
        background-color: #d4edda;
        border-left: 6px solid #28a745;
        margin: 1rem 0;
        color: #155724;
        font-weight: 500;
    }
    .answer-box {
        padding: 2rem;
        border-radius: 12px;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-left: 6px solid #667eea;
        margin: 1rem 0;
        line-height: 1.8;
        color: #2c3e50;
        font-size: 1.05rem;
    }
    .question-box {
        padding: 1.5rem;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        color: white;
        font-weight: 500;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .source-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        background-color: #3498db;
        color: white;
        border-radius: 8px;
        font-size: 0.95rem;
        font-weight: 500;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    .metric-card h3 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .metric-card p {
        margin: 0.5rem 0 0 0;
        font-size: 0.9rem;
        opacity: 0.95;
    }
    .doc-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
        border-radius: 6px;
        color: #1b5e20;
        font-weight: 500;
    }
    .file-details {
        padding: 1.5rem;
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 6px solid #2196f3;
        color: #0d47a1;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-size: 1.1rem;
        font-weight: 600;
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    .stTextArea textarea {
        border: 2px solid #667eea;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)


def save_uploaded_pdf(file) -> Path:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / file.name
    file_bytes = file.getbuffer()
    file_path.write_bytes(file_bytes)
    return file_path


def _inngest_api_base() -> str:
    """Get Inngest API base URL from secrets or environment"""
    try:
        return st.secrets.get("INNGEST_API_BASE", "https://api.inngest.com/v1")
    except (AttributeError, FileNotFoundError):
        return os.getenv("INNGEST_API_BASE", "https://api.inngest.com/v1")


def _inngest_event_key() -> str:
    """Get Inngest event key from secrets or environment"""
    try:
        return st.secrets.get("INNGEST_EVENT_KEY", "")
    except (AttributeError, FileNotFoundError):
        return os.getenv("INNGEST_EVENT_KEY", "fnse8_bu_-VVRLPxI3MH9FEBlc6mHE9AD_bEMl7NeYjZAHH4V6S7BGEsdrsDwRVjNfbEaetQq7-qBDD8BFc7AA")


async def send_rag_ingest_event(pdf_path: Path) -> str:
    """Send ingest event to Inngest Cloud"""
    url = f"{_inngest_api_base()}/events"
    
    payload = {
        "name": "rag/ingest_pdf",
        "data": {
            "pdf_path": str(pdf_path.resolve()),
            "source_id": pdf_path.name,
        },
    }
    
    headers = {
        "Authorization": f"Bearer {_inngest_event_key()}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["ids"][0]


async def send_rag_query_event(question: str, top_k: int) -> str:
    """Send query event to Inngest Cloud"""
    url = f"{_inngest_api_base()}/events"
    
    payload = {
        "name": "rag/query_pdf",
        "data": {
            "question": question,
            "top_k": top_k,
        },
    }
    
    headers = {
        "Authorization": f"Bearer {_inngest_event_key()}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["ids"][0]


def fetch_runs(event_id: str) -> list[dict]:
    """Fetch runs from Inngest Cloud"""
    url = f"{_inngest_api_base()}/events/{event_id}/runs"
    
    headers = {
        "Authorization": f"Bearer {_inngest_event_key()}",
    }
    
    import requests
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def wait_for_run_output(event_id: str, timeout_s: float = 120.0, poll_interval_s: float = 0.5) -> dict:
    start = time.time()
    last_status = None
    while True:
        runs = fetch_runs(event_id)
        if runs:
            run = runs[0]
            status = run.get("status")
            last_status = status or last_status
            if status in ("Completed", "Succeeded", "Success", "Finished"):
                return run.get("output") or {}
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"Function run {status}")
        if time.time() - start > timeout_s:
            raise TimeoutError(f"Timed out waiting for run output (last status: {last_status})")
        time.sleep(poll_interval_s)


# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = []

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/artificial-intelligence.png", width=150)
    st.title("📚 DocuMind AI")
    st.markdown("---")
    
    # Stats
    st.subheader("📊 Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(st.session_state.uploaded_docs)}</h3>
            <p>Documents</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(st.session_state.chat_history)}</h3>
            <p>Questions</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Uploaded documents list
    if st.session_state.uploaded_docs:
        st.subheader("📄 Uploaded Documents")
        for doc in st.session_state.uploaded_docs:
            st.markdown(f'<div class="doc-item">✅ {doc}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Clear history button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.markdown("---")
    st.caption("Powered by OpenAI, Qdrant & Inngest")

# Main content
st.title("🤖 DocuMind AI - Your Intelligent Document Assistant")
st.markdown("Upload your study materials and ask questions to get instant answers!")

# Create tabs
tab1, tab2 = st.tabs(["📤 Upload Documents", "💬 Ask Questions"])

# Tab 1: Upload
with tab1:
    st.markdown("### 📄 Upload PDF Document")
    st.markdown("Upload your PDF files to add them to the knowledge base.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            accept_multiple_files=False,
            help="Upload a PDF document to ingest into the RAG system"
        )
    
    with col2:
        st.info("**Supported Format:**\n- PDF files only\n- Max size: 200MB")
    
    if uploaded is not None:
        # Show file info
        file_size = len(uploaded.getvalue()) / (1024 * 1024)  # MB
        st.markdown(f"""
        <div class="file-details">
            <strong>📎 File Details:</strong><br/>
            📝 Name: <strong>{uploaded.name}</strong><br/>
            📏 Size: <strong>{file_size:.2f} MB</strong><br/>
            📄 Type: <strong>{uploaded.type}</strong>
        </div>
        """, unsafe_allow_html=True)
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("🚀 Upload & Process", type="primary", use_container_width=True):
                with st.spinner("🔄 Uploading and processing your document..."):
                    progress_bar = st.progress(0)
                    for i in range(100):
                        time.sleep(0.01)
                        progress_bar.progress(i + 1)
                    
                    try:
                        path = save_uploaded_pdf(uploaded)
                        asyncio.run(send_rag_ingest_event(path))
                        time.sleep(0.3)
                        
                        # Add to session state
                        if path.name not in st.session_state.uploaded_docs:
                            st.session_state.uploaded_docs.append(path.name)
                        
                        progress_bar.empty()
                        
                        st.markdown(f"""
                        <div class="success-box">
                            <strong>✅ Success!</strong><br/>
                            Document "{path.name}" has been uploaded and is being processed.
                        </div>
                        """, unsafe_allow_html=True)
                        st.balloons()
                    except Exception as e:
                        progress_bar.empty()
                        st.error(f"❌ Error uploading document: {str(e)}")

# Tab 2: Ask Questions
with tab2:
    st.markdown("### 💬 Ask Questions About Your Documents")
    
    # Display chat history
    if st.session_state.chat_history:
        st.markdown("#### 📜 Conversation History")
        for i, chat in enumerate(st.session_state.chat_history):
            with st.container():
                # Question
                st.markdown(f"""
                <div class="question-box">
                    <strong>🙋 You:</strong> {chat['question']}
                </div>
                """, unsafe_allow_html=True)
                
                # Answer
                st.markdown(f"""
                <div class="answer-box">
                    <strong>🤖 Assistant:</strong><br/><br/>
                    {chat['answer']}
                </div>
                """, unsafe_allow_html=True)
                
                # Sources
                if chat.get("sources"):
                    with st.expander("📚 View Sources", expanded=False):
                        for s in chat["sources"]:
                            st.markdown(f'<div class="source-item">📄 {s}</div>', unsafe_allow_html=True)
                
                st.markdown("---")
    
    # Query form
    st.markdown("#### ❓ Ask a New Question")
    
    with st.form("rag_query_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            question = st.text_area(
                "Your question",
                placeholder="e.g., What is the main topic of the document?",
                height=100,
                label_visibility="collapsed"
            )
        
        with col2:
            top_k = st.slider(
                "Context chunks",
                min_value=1,
                max_value=20,
                value=5,
                help="Number of relevant chunks to retrieve"
            )
            
            submitted = st.form_submit_button("🔍 Get Answer", type="primary", use_container_width=True)
        
        if submitted and question.strip():
            with st.spinner("🤔 Thinking... Generating answer from your documents..."):
                try:
                    event_id = asyncio.run(send_rag_query_event(question.strip(), int(top_k)))
                    output = wait_for_run_output(event_id)
                    answer = output.get("answer", "")
                    sources = output.get("sources", [])
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "question": question.strip(),
                        "answer": answer,
                        "sources": sources
                    })
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Empty state
    if not st.session_state.chat_history:
        st.info("👆 Ask a question above to get started!")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #2c3e50; padding: 2rem;">
    <p style="font-size: 1.1rem; font-weight: 600;">🚀 Built with Streamlit, OpenAI, Qdrant & Inngest</p>
    <p style="font-size: 0.9rem; color: #667eea;">💡 Tip: Upload multiple documents to create a comprehensive knowledge base</p>
</div>
""", unsafe_allow_html=True)