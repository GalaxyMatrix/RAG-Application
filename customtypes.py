import pydantic


class RAGChunkANDSrc(pydantic.BaseModel):
    chunks: list[str]
    source_id: str = None 



class UpsertResult(pydantic.BaseModel):
    ingested: int 



class RAGSearchResult(pydantic.BaseModel):
    contexts: list[str]
    sources: list[str]



class RAGQuerySearchResult(pydantic.BaseModel):
    answer: str
    sources: list[str]
    num_contexts: int