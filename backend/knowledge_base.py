import os
import chromadb
from openai import OpenAI
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Initialize clients
embed_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))


def chunk_document(text: str, chunk_size: int = 150, overlap: int = 20) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI."""
    response = embed_client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [item.embedding for item in response.data]


def build_knowledge_base():
    """
    Read all docs, chunk them, embed them, and store in ChromaDB.
    Called once on backend startup. Safe to call multiple times —
    clears and rebuilds the collection each time.
    """
    collection = chroma_client.get_or_create_collection(
        name="shopflow_docs",
        metadata={"hnsw:space": "cosine"}
    )

    # Clear existing docs so rebuild is idempotent
    existing = collection.get()
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    all_ids = []
    all_texts = []
    all_embeddings = []
    all_metadata = []

    for doc_path in DOCS_DIR.glob("*.md"):
        text = doc_path.read_text(encoding="utf-8")
        chunks = chunk_document(text)

        print(f"  {doc_path.name}: {len(chunks)} chunks")

        embeddings = embed_texts(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            all_ids.append(f"{doc_path.stem}-{i}")
            all_texts.append(chunk)
            all_embeddings.append(embedding)
            all_metadata.append({"source": doc_path.name})

    collection.add(
        ids=all_ids,
        documents=all_texts,
        embeddings=all_embeddings,
        metadatas=all_metadata
    )

    print(f"✓ Knowledge base built: {len(all_ids)} chunks across {len(list(DOCS_DIR.glob('*.md')))} docs")


def search_knowledge_base(query: str, n_results: int = 3) -> dict:
    """
    Embed the query and retrieve the most relevant doc chunks.
    Returns the chunks and their sources.
    """
    try:
        collection = chroma_client.get_collection("shopflow_docs")
    except Exception:
        return {"error": "Knowledge base not initialized", "results": []}

    query_embedding = embed_texts([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    chunks = results["documents"][0]
    sources = [m["source"] for m in results["metadatas"][0]]
    distances = results["distances"][0]

    return {
        "results": [
            {
                "content": chunk,
                "source": source,
                "relevance": round(1 - distance, 3)
            }
            for chunk, source, distance in zip(chunks, sources, distances)
        ]
    }