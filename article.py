from datetime import datetime
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from datetime import datetime
import json
import re


class Article:
    COLLECTION_NAME = "articles"

    def __init__(
        self,
        source: str,
        title: str,
        summary: str,
        body: str,
        url: str,
        published: datetime,
    ):
        if not isinstance(published, datetime):
            published = datetime.now()
        self.source = source
        self.title = title
        self.summary = summary
        self.body = body
        self.url = url
        self.published = published
        self.embedding = None

    def to_json(self):
        data = {
            "url": self.url,
            "published": self.published.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
        }
        return json.dumps(data, ensure_ascii=False)

    def id(self):
        return re.sub(
            r"[^\w\-]", "_", self.url.replace("https://", "").replace("http://", "")
        )

    def vectorize(self, model_name: str):
        content = self.to_json()
        response = genai.embed_content(model=model_name, content=content)
        embedding = response["embedding"]
        self.embedding = Vector(embedding)
        return self

    def save(self, doc_ref: firestore.DocumentReference):
        doc_ref.set(
            {
                "source": self.source,
                "title": self.title,
                "summary": self.summary,
                "body": self.body,
                "url": self.url,
                "published": self.published,
                "embedding": self.embedding,
            }
        )
        return doc_ref
