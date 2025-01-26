from datetime import datetime
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from datetime import datetime
import json
import re


class Article:
    COLLECTION = "articles"

    def __init__(
        self,
        title: str,
        summary: str,
        url: str,
        source: str = None,
        body: str = None,
        published: datetime = None,
        embedding: Vector = None,
        id: str = None,
    ):
        self.id = id if id else self.create_id(url)
        self.source = source
        self.title = title
        self.summary = summary
        self.body = body
        self.url = url
        self.published = published if published else datetime.now()
        self.embedding = embedding

    def to_json(self):
        data = {
            "url": self.url,
            "published": self.published.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
        }
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def create_id(url):
        return re.sub(
            r"[^\w\-]", "_", url.replace("https://", "").replace("http://", "")
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

    @staticmethod
    def from_dict(source):
        return Article(
            id=source.get("id"),
            title=source.get("title", ""),
            url=source.get("url", ""),
            summary=source.get("summary", ""),
            body=source.get("body"),
            embedding=source.get("embedding"),
            published=source.get("published", datetime.now()),
            source=source.get("source"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "body": self.body,
            "embedding": self.embedding,
            "published": self.published,
            "source": self.source,
        }

    def save(self, ref):
        doc_ref = ref.document(self.id)
        doc_ref.set(self.to_dict())

    def update(self, ref, updates):
        doc_ref = ref.document(self.id)
        doc_ref.update(updates)

    @staticmethod
    def get(ref, id):
        doc = ref.document(id).get()
        if doc.exists:
            data = doc.to_dict()
            return Article.from_dict(data)
        else:
            return None

    @staticmethod
    def collection(db):
        return db.collection(Article.COLLECTION)


# import firebase_admin
# from firebase_admin import firestore
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# ref = Article.collection(db)
# id = "careers_arsenal_com_jobs_5434108-research-engineer"
# article = Article.get(ref, id)
# print(article.to_dict())
