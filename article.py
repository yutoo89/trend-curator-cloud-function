from datetime import datetime
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from datetime import datetime
import json
import re
from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner


class Article:
    COLLECTION = "articles"
    MAX_LENGTH = 3000
    EMBEDDING_MODEL = "models/text-embedding-004"

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

    def to_json_for_embedding(self):
        data = {
            "title": self.title,
            "summary": self.summary,
        }
        if self.body:
            data["body"] = self.body
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def create_id(url):
        return re.sub(
            r"[^\w\-]", "_", url.replace("https://", "").replace("http://", "")
        )

    def vectorize(self, ref):
        if self.embedding:
            return
        content = self.to_json_for_embedding()
        response = genai.embed_content(model=self.EMBEDDING_MODEL, content=content)
        embedding = response["embedding"]
        self.update(ref, {"embedding": Vector(embedding)})

    def import_body(self, ref, cleaner: ArticleCleaner):
        body = self.body
        if body:
            return
        try:
            body = ArticleContentFetcher.fetch(self.url)
            body = cleaner.clean_text(body)[: self.MAX_LENGTH]
            body = cleaner.llm_clean_text(body, self.title)
        except Exception as e:
            print(f"[ERROR] Failed to fetch or clean body for URL '{self.url}': {e}")
        self.update(ref, {"body": body})

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

    @staticmethod
    def exists(ref, id):
        doc_ref = ref.document(id)
        return doc_ref.get().exists


# import os
# import firebase_admin
# from firebase_admin import firestore
# import google.generativeai as genai

# genai.configure(api_key=os.environ["GENAI_API_KEY"])
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# ref = Article.collection(db)
# id = "careers_arsenal_com_jobs_5434108-research-engineer"
# article = Article.get(ref, id)
# print(article.to_dict())
# # article.vectorize(ref)
