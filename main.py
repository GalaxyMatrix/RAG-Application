import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import inngest
import inngest.fast_api
from dotenv import load_dotenv
import uuid
import os
import datetime
import base64
import tempfile
from openai import OpenAI
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from customtypes import RAGChunkANDSrc, UpsertResult, RAGSearchResult, RAGQuerySearchResult

load_dotenv()

# Configure Inngest for production
inngest_client = inngest.Inngest(
    app_id='rag_app',
    logger=logging.getLogger('uvicorn'),
    is_production=True,  # Set to True for cloud mode
    event_key=os.getenv("INNGEST_EVENT_KEY"),  # Add event key
    signing_key=os.getenv("INNGEST_SIGNING_KEY")  # Add signing key
)

@inngest_client.create_function(
    fn_id='RAG: ingest PDF',
    trigger=inngest.TriggerEvent(event='rag/ingest_pdf'),
    throttle=inngest.Throttle(
        count=2,
        period=datetime.timedelta(minutes=1)
    ),
    rate_limit=inngest.RateLimit(
        limit=1,
        period=datetime.timedelta(hours=4),
        key="event.data.source_id"
    )
)
async def rag_ingest_pdf(ctx, step):
    def _load() -> dict:
        # Get PDF content from event (base64 encoded)
        pdf_content = ctx.event.data.get("pdf_content")
        source_id = ctx.event.data.get("source_id")
        
        # Decode base64 and save to temporary file
        pdf_bytes = base64.b64decode(pdf_content)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            chunks = load_and_chunk_pdf(tmp_path)
            return RAGChunkANDSrc(chunks=chunks, source_id=source_id).model_dump()
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _upsert(chunks_and_src: dict) -> dict:
        chunks = chunks_and_src["chunks"]
        source_id = chunks_and_src["source_id"]
        vecs = embed_texts(chunks)
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, name=f"{source_id}:{i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
        QdrantStorage().upsert(ids, vecs, payloads)
        return UpsertResult(ingested=len(chunks)).model_dump()

    chunks_and_src = await step.run('load_and_chunk', _load)
    ingested = await step.run("embed_and_upsert", lambda: _upsert(chunks_and_src))
    return ingested


@inngest_client.create_function(
    fn_id='RAG: Query PDF',
    trigger=inngest.TriggerEvent(event='rag/query_pdf')
)
async def rag_query_pdf(ctx, step):
    def _search(question: str, top_k: int = 5) -> dict:
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k=top_k)
        return found  # Already a dict
    
    def _generate_answer(found: dict, question: str) -> str:
        context_block = "\n\n".join(f"- {c}" for c in found["contexts"])
        user_content = (
            "Use the following context to answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {question}\n"
            "Answer concisely using the context above."
        )

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You answer questions using only the provided context."},
                {"role": "user", "content": user_content}
            ]
        )
        return response.choices[0].message.content.strip()
    
    question = ctx.event.data['question']
    top_k = ctx.event.data.get('top_k', 5)

    found = await step.run('embed-and-search', lambda: _search(question, top_k))
    answer = await step.run('llm-answer', lambda: _generate_answer(found, question))
    
    return {
        "answer": answer,
        "sources": found["sources"],
        "num_contexts": len(found["contexts"])
    }


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# NEW: Direct upload endpoint
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Direct PDF upload endpoint that processes synchronously"""
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Read file content
        pdf_bytes = await file.read()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            # Process PDF
            chunks = load_and_chunk_pdf(tmp_path)
            source_id = file.filename
            
            # Embed and store
            vecs = embed_texts(chunks)
            ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, name=f"{source_id}:{i}")) for i in range(len(chunks))]
            payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
            QdrantStorage().upsert(ids, vecs, payloads)
            
            return {
                "status": "success",
                "message": f"Successfully processed {file.filename}",
                "chunks_processed": len(chunks),
                "source_id": source_id
            }
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query_documents(question: str, top_k: int = 5, source_filter: str = None):
    """Direct synchronous query endpoint - returns answer immediately"""
    try:
        # Search vector DB
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        
        # Apply source filter if provided
        if source_filter and source_filter != "all":
            found = store.search_with_filter(query_vec, top_k=top_k, source_filter=source_filter)
        else:
            found = store.search(query_vec, top_k=top_k)
        
        # Generate answer with OpenAI
        context_block = "\n\n".join(f"- {c}" for c in found["contexts"])
        user_content = (
            "Use the following context to answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {question}\n"
            "Answer concisely using the context above."
        )

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You answer questions using only the provided context."},
                {"role": "user", "content": user_content}
            ]
        )
        answer = response.choices[0].message.content.strip()
        
        return {
            "status": "completed",
            "answer": answer,
            "sources": found["sources"],
            "num_contexts": len(found["contexts"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
@app.head("/")
async def root():
    return {
        "message": "RAG AI Agent API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "upload": "/upload",
            "inngest": "/api/inngest"
        }
    }


@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "healthy"}


@app.get("/result/{event_id}")
async def get_result(event_id: str):
    """Fetch Inngest function result by event ID"""
    import httpx
    
    try:
        # Use Inngest's runs API endpoint
        inngest_url = f"https://api.inngest.com/v1/events/{event_id}/runs"
        headers = {
            "Authorization": f"Bearer {os.getenv('INNGEST_EVENT_KEY')}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(inngest_url, headers=headers)
            
            # Log response for debugging
            print(f"Inngest API response status: {response.status_code}")
            print(f"Inngest API response: {response.text[:500]}")
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=500,
                    detail="Invalid Inngest Event Key - check INNGEST_EVENT_KEY environment variable"
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Inngest API error ({response.status_code}): {response.text[:200]}"
                )
            
            data = response.json()
            
            # Check if there are any runs
            runs = data.get("data", [])
            if not runs or len(runs) == 0:
                return {
                    "status": "processing",
                    "message": "No runs found yet, still processing"
                }
            
            # Get the first (most recent) run
            run = runs[0]
            run_status = run.get("status", "").lower()
            
            print(f"Run status: {run_status}")
            
            # If still running, return 202 Accepted
            if run_status in ["running", "queued", "started"]:
                return {
                    "status": "processing",
                    "message": "Function is still running"
                }
            
            # If completed, return the output
            if run_status == "completed":
                output = run.get("output")
                if output:
                    return {
                        "status": "completed",
                        "answer": output.get("answer", "No answer generated"),
                        "sources": output.get("sources", []),
                        "num_contexts": output.get("num_contexts", 0)
                    }
                else:
                    return {
                        "status": "completed",
                        "answer": "Function completed but no output was returned",
                        "sources": [],
                        "num_contexts": 0
                    }
            
            # If failed
            if run_status == "failed":
                error_msg = run.get("error", "Unknown error")
                return {
                    "status": "error",
                    "message": f"Function execution failed: {error_msg}",
                    "answer": "An error occurred while processing your question",
                    "sources": []
                }
            
            # Unknown status - still processing
            return {
                "status": "processing",
                "message": f"Current status: {run_status}"
            }
            
    except httpx.HTTPError as e:
        print(f"HTTP error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"HTTP error connecting to Inngest: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching result: {str(e)}")


inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf])