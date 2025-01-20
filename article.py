from __future__ import annotations
from datetime import datetime, timezone
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector


class Article:
    EMBEDDING_MODEL = "models/text-embedding-004"
    COLLECTION_NAME = "articles"

    def __init__(
        self, title: str, body: str, url: str, doc_ref: firestore.DocumentReference
    ):
        self.title = title
        self.body = body
        self.url = url
        self.doc_ref = doc_ref

    @staticmethod
    def bulk_create(db: firestore.Client, articles: list):
        articles_collection = db.collection(Article.COLLECTION_NAME)

        for article in articles:
            articles_collection.add(
                {
                    "title": article["title"],
                    "url": article["url"],
                    "body": article["body"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    def vectorize(self, model_name: str = EMBEDDING_MODEL):
        if model_name is None:
            model_name = self.EMBEDDING_MODEL
        content = f"Title: {self.title}\nBody: {self.body}"
        response = genai.embed_content(model=model_name, content=content)
        try:
            embedding = response["embedding"]
            print(f"[INFO] Vectorization successful for title: {self.title}")
            self.doc_ref.update({"embedding": Vector(embedding)})
            return embedding
        except Exception as e:
            print(f"[ERROR] Failed to vectorize article: {e}")
            return None
