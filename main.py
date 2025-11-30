import logging
from fastapi import FastAPI
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
            "inngest": "/api/inngest"
        }
    }

@app.get("/health")
@app.head("/health")
async def health():
    return {"status": "healthy"}


inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf])