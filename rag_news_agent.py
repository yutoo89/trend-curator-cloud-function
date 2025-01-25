import os
import vertexai
from vertexai.preview import rag
from vertexai.preview.generative_models import GenerativeModel, Tool

# 定数設定
PROJECT_ID = os.getenv("PROJECT_ID")
BUCKET_NAME = "trend-curator-articles"
RAG_CORPUS_NAME = os.getenv("RAG_CORPUS_NAME")
VERTEX_AI_LOCATION = os.getenv("VERTEX_AI_LOCATION", "us-central1")
PUBLISHER_MODEL = "publishers/google/models/text-embedding-004"
RAG_CHUNK_SIZE = 512
RAG_CHUNK_OVERLAP = 100
RAG_MAX_EMBEDDING_REQUESTS_PER_MIN = 900

print("Initializing Vertex AI API...")
vertexai.init(project=PROJECT_ID, location=VERTEX_AI_LOCATION)
print("Vertex AI API initialized.")


class RAGNewsAgent:
    def __init__(self):
        self.rag_retrieval_tool = self._create_rag_retrieval_tool()
        self.rag_model = self._create_generative_model()

    def _create_rag_retrieval_tool(self):
        return Tool.from_retrieval(
            retrieval=rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[
                        rag.RagResource(
                            rag_corpus=RAG_CORPUS_NAME,
                        )
                    ],
                    similarity_top_k=3,
                    vector_distance_threshold=0.5,
                ),
            )
        )

    def _create_generative_model(self):
        return GenerativeModel(
            model_name="gemini-1.5-flash-001", tools=[self.rag_retrieval_tool]
        )

    def generate_response(self, query):
        response = self.rag_model.generate_content(query)
        return response.text


# Example Usage
# agent = RAGNewsAgent()
# query = "最近のおすすめのAIツールは？"
# response = agent.generate_response(query)
# print("Generated Response:", response)
