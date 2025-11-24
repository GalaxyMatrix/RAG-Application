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

load_dotenv()

inngest_client = inngest.Inngest(
    app_id='rag_app',
    logger=logging.getLogger('uvicorn'),
    is_production=False,
    serializer=inngest.PydanticSerializer()
)

@inngest_client.create_function(
    fn_id='RAG: ingest PDF',
    trigger=inngest.TriggerEvent(event='rag/ingest_pdf'),
    throttle=inngest.Throttle(
        limit=2,
        period=datetime.timedelta(minutes=1)
    ),
    rate_limit=inngest.RateLimit(
        limit=1,
        period=datetime.timedelta(hours=4),
        key="event.data.source_id"
    )
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
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, name=f"{source_id}:{i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
        QdrantStorage().upsert(ids, vecs, payloads)
        return UpsertResult(ingested=len(chunks))

    chunks_and_src = await ctx.step.run('load_and_chunk', lambda: _load(ctx), output_type=RAGChunkANDSrc)
    ingested = await ctx.step.run("embed_and_upsert", lambda: _upsert(chunks_and_src), output_type=UpsertResult)
    return ingested.model_dump()


@inngest_client.create_function(
    fn_id='RAG: Query PDF',
    trigger=inngest.TriggerEvent(event='rag/query_pdf')
)
async def rag_query_pdf(ctx: inngest.Context):
    def _search(question: str, top_k: int = 5) -> RAGSearchResult:
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k=top_k)
        return RAGSearchResult(**found)
    
    question = ctx.event.data['question']
    top_k = ctx.event.data.get('top_k', 5)

    found = await ctx.step.run('embed-and-search', lambda: _search(question, top_k), output_type=RAGSearchResult)
    
    context_block = "\n\n".join(f"- {c}" for c in found.contexts)
    user_content = (
        "Use the following context to answer the question.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n"
        "Answer concisely using the context above."
    )

    adapter = ai.openai.Adapter(
        auth_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini"
    )

    res = await ctx.step.ai.infer(
        "llm-answer",
        adapter=adapter,
        body={
            "max_tokens": 1024,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "You answer questions using only the provided context."},
                {"role": "user", "content": user_content}
            ]
        }
    )

    answer = res["choices"][0]["message"]["content"].strip()
    
    return RAGQuerySearchResult(
        answers=answer,
        sources=found.sources,
        num_contexts=len(found.contexts)
    ).model_dump()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
async def root():
    return {
        "message": "RAG AI Agent API",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "inngest": "/api/inngest"
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}


inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf])