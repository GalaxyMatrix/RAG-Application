import asyncio
from pathlib import Path
import time
import base64
import requests

import streamlit as st
from dotenv import load_dotenv
import os
import inngest

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
    .info-box {
        padding: 1.5rem;
        border-radius: 12px;
        background-color: #d1ecf1;
        border-left: 6px solid #0c5460;
        margin: 1rem 0;
        color: #0c5460;
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


@st.cache_resource
def get_inngest_client():
    """Get Inngest client with proper configuration"""
    try:
        event_key = st.secrets.get("INNGEST_EVENT_KEY", "")
    except (AttributeError, FileNotFoundError):
        event_key = os.getenv("INNGEST_EVENT_KEY", "")
    
    return inngest.Inngest(
        app_id="rag_app",
        event_key=event_key,
        is_production=True
    )


def get_backend_url():
    """Get backend API URL"""
    try:
        return st.secrets.get("BACKEND_URL", "https://documentai-416p.onrender.com")
    except (AttributeError, FileNotFoundError):
        return os.getenv("BACKEND_URL", "https://documentai-416p.onrender.com")


def save_uploaded_pdf(file) -> Path:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / file.name
    file_bytes = file.getbuffer()
    file_path.write_bytes(file_bytes)
    return file_path


def send_event_sync(event_name: str, data: dict) -> str:
    """Synchronous wrapper for sending events to Inngest"""
    client = get_inngest_client()
    
    # Create a new event loop if needed
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Send event
    async def _send():
        result = await client.send(inngest.Event(name=event_name, data=data))
        return result[0] if result else None
    
    return loop.run_until_complete(_send())


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
                    for i in range(50):
                        time.sleep(0.01)
                        progress_bar.progress(i + 1)
                    
                    try:
                        # Prepare file for upload
                        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
                        
                        # Send to backend API
                        backend_url = get_backend_url()
                        response = requests.post(f"{backend_url}/upload", files=files, timeout=120)
                        
                        for i in range(50, 100):
                            time.sleep(0.01)
                            progress_bar.progress(i + 1)
                        
                        response.raise_for_status()
                        result = response.json()
                        
                        # Add to session state
                        if uploaded.name not in st.session_state.uploaded_docs:
                            st.session_state.uploaded_docs.append(uploaded.name)
                        
                        progress_bar.empty()
                        
                        st.markdown(f"""
                        <div class="success-box">
                            <strong>✅ Success!</strong><br/>
                            Document "{uploaded.name}" has been processed successfully.<br/>
                            Chunks processed: {result.get('chunks_processed', 'N/A')}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.balloons()
                    except requests.exceptions.RequestException as e:
                        progress_bar.empty()
                        st.error(f"❌ Error uploading document: {str(e)}")
                    except Exception as e:
                        progress_bar.empty()
                        st.error(f"❌ Error: {str(e)}")

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
                
                # Check if pending and try to fetch result
                if chat.get("pending"):
                    event_id = chat.get('event_id')
                    
                    # Try to fetch result from backend
                    try:
                        backend_url = get_backend_url()
                        result_response = requests.get(
                            f"{backend_url}/result/{event_id}",
                            timeout=10
                        )
                        
                        if result_response.status_code == 200:
                            result = result_response.json()
                            
                            # Check if the result is completed
                            if result.get('status') == 'completed':
                                # Update chat history with result
                                st.session_state.chat_history[i] = {
                                    "question": chat['question'],
                                    "answer": result.get('answer', 'No answer generated'),
                                    "sources": result.get('sources', []),
                                    "pending": False
                                }
                                st.rerun()
                            else:
                                # Still processing - show with auto-refresh
                                st.markdown(f"""
                                <div class="info-box">
                                    ⏳ <strong>Processing...</strong><br/>
                                    Your question is being processed. Event ID: {event_id}<br/>
                                    <small>Auto-refreshing every 3 seconds...</small>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Auto-refresh after 3 seconds
                                time.sleep(3)
                                st.rerun()
                    except Exception as e:
                        st.markdown(f"""
                        <div class="info-box">
                            ⏳ <strong>Processing...</strong><br/>
                            Event ID: {event_id}<br/>
                            <small>Checking for results... (will auto-refresh)</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Auto-refresh after 3 seconds
                        time.sleep(3)
                        st.rerun()
                else:
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
            with st.spinner("🤔 Getting your answer..."):
                try:
                    backend_url = get_backend_url()
                    response = requests.post(
                        f"{backend_url}/query",
                        params={"question": question.strip(), "top_k": int(top_k)},
                        timeout=60
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "question": question.strip(),
                        "answer": result.get('answer', 'No answer generated'),
                        "sources": result.get('sources', []),
                        "pending": False
                    })
                    
                    st.success("✅ Answer received!")
                    time.sleep(0.5)
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
    <p style="font-size: 0.9rem; color: #667eea;">💡 Tip: Answers appear automatically once processing is complete</p>
</div>
""", unsafe_allow_html=True)