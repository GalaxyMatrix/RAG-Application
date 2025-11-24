import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
from typing import List
import re

load_dotenv()
client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536  # text-embedding-3-small dimension

def load_and_chunk_pdf(path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    """
    Load PDF and split into chunks using PyMuPDF.
    
    Args:
        path: Path to the PDF file
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of overlapping characters between chunks
    
    Returns:
        List of text chunks
    """
    # Open PDF
    doc = fitz.open(path)
    texts = []
    
    # Extract text from each page
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if text.strip():
            texts.append(text)
    
    doc.close()
    
    # Combine all text
    full_text = "\n\n".join(texts)
    
    # Split into chunks with overlap
    chunks = []
    start = 0
    
    while start < len(full_text):
        end = start + chunk_size
        chunk = full_text[start:end]
        
        # Try to break at sentence boundary
        if end < len(full_text):
            # Look for sentence endings
            last_period = chunk.rfind('. ')
            last_newline = chunk.rfind('\n')
            last_break = max(last_period, last_newline)
            
            if last_break > chunk_size * 0.5:  # Only break if we're at least halfway
                chunk = chunk[:last_break + 1]
                end = start + last_break + 1
        
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - chunk_overlap
    
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using OpenAI.
    
    Args:
        texts: List of text strings to embed
    
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts
    )
    
    return [item.embedding for item in response.data]
