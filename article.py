import os
import re
import json
from datetime import datetime
from typing import List
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from datetime import datetime
from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner
from article_summary_generator import ArticleSummaryGenerator
from web_searcher import WebSearcher


class Article:
    COLLECTION = "articles"
    MAX_LENGTH = 2000
    EMBEDDING_MODEL = "models/text-embedding-004"
    BYTE_LIMIT = 3000  # embed_contentのペイロードサイズ上限が10,000バイト

    def __init__(
        self,
        title: str,
        summary: str,
        url: str,
        source: str = None,
        body: str = None,
        keyword: str = None,
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
        self.keyword = keyword
        self.published = published if published else datetime.now()
        self.embedding = embedding

    def to_json_for_embedding(self):
        data = {
            "title": self.title,
            "summary": self.summary,
            "body": self.body if self.body else "",
        }

        while True:
            json_data = json.dumps(data, ensure_ascii=False)
            byte_size = len(json_data.encode("utf-8"))

            if byte_size <= self.BYTE_LIMIT:
                break

            if data["body"]:
                data["body"] = data["body"][: len(data["body"]) - 100]
            elif data["summary"]:
                data["summary"] = data["summary"][: len(data["summary"]) - 100]
            elif data["title"]:
                data["title"] = data["title"][: len(data["title"]) - 100]
            else:
                break

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
        keyword = self.keyword
        if body and keyword:
            return
        try:
            body = ArticleContentFetcher.fetch(self.url)
            body = cleaner.clean_text(body)[: self.MAX_LENGTH]
            clean_result = cleaner.llm_clean_text(body, self.title)
            body = clean_result.get("clean_text", "")
            keyword = clean_result.get("keyword", "")
        except Exception as e:
            print(f"[ERROR] Failed to fetch or clean body for URL '{self.url}': {e}")
        self.update(ref, {"body": body, "keyword": keyword})

    @staticmethod
    def from_dict(source):
        return Article(
            id=source.get("id"),
            title=source.get("title", ""),
            url=source.get("url", ""),
            summary=source.get("summary", ""),
            body=source.get("body"),
            keyword=source.get("keyword"),
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
            "keyword": self.keyword,
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

    @staticmethod
    def create_by_query(query: str) -> List['Article']:
        google_custom_search_api_key = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
        google_search_cse_id = os.environ["GOOGLE_SEARCH_CSE_ID"]
        searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)
        content_fetcher = ArticleContentFetcher()
        cleaner = ArticleCleaner('gemini-2.0-flash-exp')
        summary_generator = ArticleSummaryGenerator('gemini-2.0-flash-exp')
        ref = Article.collection(firestore.client())

        # Perform the search and get the top 3 results
        search_results = searcher.search(query, num_results=3)
        articles = []

        for result in search_results:
            title = result["title"]
            url = result["url"]

            try:
                # Fetch the article content
                raw_content = content_fetcher.fetch(url)
                if not raw_content:
                    continue

                # Clean the content
                clean_result = cleaner.llm_clean_text(raw_content, title)
                clean_text = clean_result.get("clean_text", "")
                keyword = clean_result.get("keyword", "")
                summary = summary_generator.generate_summary(title, clean_text)

                # Create an Article instance
                article = Article(
                    title=title,
                    summary=summary,
                    url=url,
                    body=clean_text,
                    keyword=keyword,
                )
                article.save(ref)
                articles.append(article)

            except Exception as e:
                print(f"Failed to process article at {url}: {e}")

        return articles
