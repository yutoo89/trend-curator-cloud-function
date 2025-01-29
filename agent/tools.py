import json
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud import firestore

from article import Article
from conversation_record import ConversationRecord
from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner
from article_summary_generator import ArticleSummaryGenerator
from web_searcher import WebSearcher


OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": "Search articles relevant to the query from the article DB",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string to find related articles",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_recent_messages",
            "description": "Get the recent conversation history for the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_by_query",
            "description": "Perform a web search for the query and create new articles in Firestore",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string to create articles from.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def clean_url(url: str) -> str:
    return url.split("?")[0]


def format_articles(articles: list) -> str:
    """
    検索結果のリストをフォーマットして文字列にまとめる。
    """
    articles_section = ""
    for index, article in enumerate(articles):
        title = article.get("title", "")
        url = clean_url(article.get("url", ""))
        summary = article.get("summary", "")
        body = article.get("body", "")

        if index == 0:
            # 最初の1件だけ本文を多めに表示
            articles_section += (
                f"title: {title}\n"
                f"url: {url}\n"
                f"summary: {summary}\n"
                f"body: {body[:3000]}\n\n"
            )
        else:
            # 2件目以降はサマリーを短めに
            articles_section += (
                f"title: {title}\n" f"url: {url}\n" f"summary: {summary[:500]}\n\n"
            )
    return articles_section


def search_articles(article_collection, query: str) -> str:
    """
    Embedding を用いて Firestore (Vector) から記事を検索し、
    フォーマットした文字列を返す。
    """
    query_vector = genai.embed_content(model=Article.EMBEDDING_MODEL, content=query)[
        "embedding"
    ]

    vector_query = article_collection.select(
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

    return format_articles(articles)


def fetch_recent_messages(db: firestore.Client, user_id: str) -> str:
    """
    Firestore に保存されている会話履歴から指定件数を取得して整形。
    """
    recent_records = ConversationRecord.get_recent_messages(db, user_id, limit=10)
    conversation_text = "\n".join([f"{r.role}: {r.message}" for r in recent_records])
    return conversation_text


def create_by_query(
    db: firestore.Client,
    web_searcher: WebSearcher,
    content_fetcher: ArticleContentFetcher,
    article_cleaner: ArticleCleaner,
    summary_generator: ArticleSummaryGenerator,
    article_collection,
    query: str,
) -> str:
    """
    指定したクエリを元にウェブ検索を行い、
    記事を作成して Firestore に保存。
    保存した記事のタイトル一覧を返す。
    """
    search_results = web_searcher.search(query, num_results=3)
    created_titles = []

    for result in search_results:
        title = result["title"]
        url = result["url"]

        try:
            raw_content = content_fetcher.fetch(url)
            if not raw_content:
                continue

            clean_result = article_cleaner.llm_clean_text(raw_content, title)
            clean_text = clean_result.get("clean_text", "")
            keyword = clean_result.get("keyword", "")
            summary = summary_generator.generate_summary(title, clean_text)

            article = Article(
                title=title,
                summary=summary,
                url=url,
                body=clean_text,
                keyword=keyword,
            )
            article.save(article_collection)
            created_titles.append(title)

        except Exception as e:
            print(f"Failed to process article at {url}: {e}")

    if created_titles:
        return f"Created articles:\n" + "\n".join(created_titles)
    else:
        return "No articles were created."
