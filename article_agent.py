import os
from typing import List
from conversation_record import ConversationRecord
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner
from article_summary_generator import ArticleSummaryGenerator
from web_searcher import WebSearcher
from article import Article
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure


# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# Firestore 初期化
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

# Google Custom Search
google_custom_search_api_key = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
google_search_cse_id = os.environ["GOOGLE_SEARCH_CSE_ID"]


GEMINI_MODEL = "gemini-2.0-flash-exp"


class ArticleAgent:

    def __init__(self, db: firestore.Client, web_searcher: WebSearcher):
        self.db = db
        self.web_searcher = web_searcher
        self.content_fetcher = ArticleContentFetcher()
        self.article_cleaner = ArticleCleaner(GEMINI_MODEL)
        self.summary_generator = ArticleSummaryGenerator(GEMINI_MODEL)
        self.article_collection = Article.collection(self.db)

    def create_by_query(self, query: str) -> List[Article]:
        # Perform the search and get the top 3 results
        search_results = self.web_searcher.search(query, num_results=3)
        articles = []

        for result in search_results:
            title = result["title"]
            url = result["url"]

            try:
                # Fetch the article content
                raw_content = self.content_fetcher.fetch(url)
                if not raw_content:
                    continue

                # Clean the content
                clean_result = self.article_cleaner.llm_clean_text(raw_content, title)
                clean_text = clean_result.get("clean_text", "")
                keyword = clean_result.get("keyword", "")
                summary = self.summary_generator.generate_summary(title, clean_text)

                # Create an Article instance
                article = Article(
                    title=title,
                    summary=summary,
                    url=url,
                    body=clean_text,
                    keyword=keyword,
                )
                article.save(self.article_collection)
                articles.append(article)

            except Exception as e:
                print(f"Failed to process article at {url}: {e}")

        return articles

    def search_articles(self, query: str) -> str:
        """
        クエリに関連する記事をベクトル検索し、上位3件をフォーマットして返す。

        :param query: 検索クエリ文字列
        :return: 整形済みの文字列 (articles_section形式)
        """
        # クエリから埋め込みベクトルを生成
        query_vector = genai.embed_content(
            model=Article.EMBEDDING_MODEL, content=query
        )["embedding"]

        # ベクトル検索で関連する記事を取得
        vector_query = self.article_collection.select(
            ["id", "title", "summary", "body", "url", "published"]
        ).find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.EUCLIDEAN,
            limit=3,
        )

        articles = []
        for doc in vector_query.stream():
            article_data = doc.to_dict()
            if article_data and "id" in article_data:
                articles.append(article_data)

        # 記事をフォーマットして整形
        articles_section = self.format_articles(articles)
        return articles_section

    def format_articles(self, articles: list) -> str:
        """
        記事リストを指定フォーマットの文字列に変換する。

        :param articles: 記事のリスト
        :return: 整形済みの文字列 (articles_section形式)
        """
        articles_section = ""

        for index, article in enumerate(articles):
            title = article.get("title", "")
            url = self.clean_url(article.get("url", ""))
            summary = article.get("summary", "")
            body = article.get("body", "")

            if index == 0:
                # 最初の1件は body も含める
                articles_section += (
                    f"title: {title}\n"
                    f"url: {url}\n"
                    f"summary: {summary}\n"
                    f"body: {body[:3000]}\n\n"
                )
            else:
                # 2件目以降は summary のみ
                articles_section += (
                    f"title: {title}\n" f"url: {url}\n" f"summary: {summary[:500]}\n\n"
                )

        return articles_section

    def clean_url(self, url: str) -> str:
        url = url.split("?")[0]
        return url

    def get_recent_messages(self, user_id: str) -> str:
        recent_records = ConversationRecord.get_recent_messages(
            self.db, user_id, limit=10
        )
        conversation_text = "\n".join(
            [f"{r.role}: {r.message}" for r in recent_records]
        )
        return conversation_text
