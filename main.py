import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import inngest
import inngest.fast_api
from inngest.experimental import ai
from dotenv import load_dotenv
import uuid
import os
import datetime
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from customtypes import RAGChunkANDSrc, UpsertResult, RAGSearchResult, RAGQuerySearchResult
from pydantic import BaseModel


load_dotenv()


inngest_client = inngest.Inngest(
    app_id='rag-app',
    logger = logging.getLogger('uvicorn'),
    is_production = False,
    serializer = inngest.PydanticSerializer()
)

@inngest_client.create_function(
    fn_id = 'RAG: ingest PDF',
    trigger = inngest.TriggerEvent(event='rag/ingest_pdf')
)
async def rag_ingest_pdf(ctx: inngest.Context):
    def _load(ctx: inngest.Context) -> RAGChunkANDSrc:
        pdf_path = ctx.event.data["pdf_path"]
        source_id = ctx.event.data.get("source_id", pdf_path)
        chunks = load_and_chunk_pdf(pdf_path)
        return RAGChunkANDSrc(chunks=chunks, source_id=source_id)

    def _upsert(chunks_and_src: RAGChunkANDSrc) -> UpsertResult:
        chunks = chunks_and_src.chunks
        source_id = chunks_and_src.source_id
        vecs = embed_texts(chunks)
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, name=f"{source_id}: {i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
        QdrantStorage().upsert(ids, vecs, payloads)
        return UpsertResult(ingested=len(chunks))

    chunks_and_src = await ctx.step.run('load_and_chunk', lambda: _load(ctx), output_type=RAGChunkANDSrc)
    ingested = await ctx.step.run("embed_and_upsert", lambda: _upsert(chunks_and_src), output_type=UpsertResult)
    return ingested.model_dump()


@inngest_client.create_function(
    fn_id = 'RAG: Query PDF',
    trigger = inngest.TriggerEvent(event='rag/query')
)
async def rag_query_pdf(ctx: inngest.Context):
    def _search(question: str, top_k: int=5):
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k=top_k)
        return RAGSearchResult(**found)
    
    question = ctx.event.data['question']
    top_k = ctx.event.data.get('top_k', 5)

    found = await ctx.step.run('embed-and-search', lambda: _search(question, top_k), output_type=RAGSearchResult)
    
    answer = await ctx.step.ai.infer_with_tool(
        "answer-question",
        "Answer the user's question using the provided context. Be concise and accurate.",
        tools={
            "question": question,
            "context": "\n\n".join(found.contexts)
        }
    )

    return RAGQuerySearchResult(answer=answer, sources=found.sources).model_dump()


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    pdf_path: str
    source_id: str = None

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

@app.get("/")
async def root():
    return {
        "message": "RAG AI Agent API",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "ingest": "/ingest",
            "query": "/query",
            "inngest": "/api/inngest"
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/ingest")
async def ingest_pdf(request: IngestRequest):
    await inngest_client.send({
        "name": "rag/ingest_pdf",
        "data": {
            "pdf_path": request.pdf_path,
            "source_id": request.source_id or request.pdf_path
        }
    })
    return {"status": "PDF ingestion started"}

@app.post("/query")
async def query_pdf(request: QueryRequest):
    result = await inngest_client.send({
        "name": "rag/query",
        "data": {
            "question": request.question,
            "top_k": request.top_k
        }
    })
    # For demo, return mock response. In production, use webhooks or polling
    store = QdrantStorage()
    query_vec = embed_texts([request.question])[0]
    found = store.search(query_vec, top_k=request.top_k)
    return {
        "answer": f"Based on the context: {found['contexts'][0][:200]}..." if found['contexts'] else "No relevant information found",
        "sources": found['sources']
    }

inngest.fast_api.serve(app, inngest_client, functions=[rag_ingest_pdf, rag_query_pdf])
