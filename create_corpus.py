import os
import vertexai
from vertexai.preview import rag

# Configuration
PROJECT_ID = os.getenv("PROJECT_ID")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
PUBLISHER_MODEL = "publishers/google/models/text-embedding-004"
RAG_CHUNK_SIZE = 512
RAG_CHUNK_OVERLAP = 100
RAG_MAX_EMBEDDING_REQUESTS_PER_MIN = 900

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=VERTEX_AI_LOCATION)


def create_corpus_for_app():
    # Create a RAG corpus
    embedding_model_config = rag.EmbeddingModelConfig(publisher_model=PUBLISHER_MODEL)
    rag_corpus = rag.create_corpus(
        display_name=PROJECT_ID,
        embedding_model_config=embedding_model_config,
    )
    print(f"Created RAG corpus for app: {PROJECT_ID}")
    print(f"corpusName: {rag_corpus.name}")


if __name__ == "__main__":
    create_corpus_for_app()
