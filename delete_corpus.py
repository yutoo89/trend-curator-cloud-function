import os
import vertexai
from vertexai.preview import rag

PROJECT_ID = os.getenv("PROJECT_ID")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
RAG_CORPUS_NAME = os.getenv("RAG_CORPUS_NAME")

vertexai.init(project=PROJECT_ID, location=VERTEX_AI_LOCATION)
rag.delete_corpus(name=RAG_CORPUS_NAME)
print(f"Corpus {RAG_CORPUS_NAME} deleted.")
