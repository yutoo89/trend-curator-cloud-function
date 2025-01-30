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
            "name": "vector_db_article_search",
            "description": "ベクトルデータベースを用いてクエリに関連する記事を検索し、テキストとして返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索に用いるクエリ文字列",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_conversation_history",
            "description": "ユーザーとの直近の会話履歴を取得し、テキストとして返します。",
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
            "name": "get_article_title_url_list",
            "description": "指定したクエリでウェブ検索を行い、検索結果のタイトルとURLのリストを返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "ウェブ検索に用いるクエリ文字列",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_from_title_url",
            "description": "タイトルとURLを渡すと、ページ内容を要約したテキストを返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "記事のタイトル"
                    },
                    "url": {
                        "type": "string",
                        "description": "記事のURL"
                    },
                },
                "required": ["title", "url"],
            },
        },
    },
]


NEWS_GENERATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vector_db_article_search",
            "description": "ベクトルデータベースを用いてクエリに関連する記事を検索し、テキストとして返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索に用いるクエリ文字列",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_title_url_list",
            "description": "指定したクエリでウェブ検索を行い、検索結果のタイトルとURLのリストを返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "ウェブ検索に用いるクエリ文字列",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_from_title_url",
            "description": "タイトルとURLを渡すと、ページ内容を要約したテキストを返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "記事のタイトル"
                    },
                    "url": {
                        "type": "string",
                        "description": "記事のURL"
                    },
                },
                "required": ["title", "url"],
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
            articles_section += (
                f"title: {title}\n"
                f"url: {url}\n"
                f"summary: {summary}\n"
                f"body: {body[:3000]}\n\n"
            )
        else:
            articles_section += (
                f"title: {title}\n" f"url: {url}\n" f"summary: {summary[:500]}\n\n"
            )
    return articles_section


def vector_db_article_search(article_collection, query: str) -> str:
    print(f"Calling vector_db_article_search with query: {query}")
    
    query_vector = genai.embed_content(model=Article.EMBEDDING_MODEL, content=query)["embedding"]

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


def get_conversation_history(db: firestore.Client, user_id: str) -> str:
    print(f"Calling get_conversation_history with user_id: {user_id}")
    
    recent_records = ConversationRecord.get_recent_messages(db, user_id, limit=10)
    conversation_text = "\n".join([f"{r.role}: {r.message}" for r in recent_records])
    return conversation_text


def get_article_title_url_list(
    web_searcher: WebSearcher,
    query: str,
) -> str:
    print(f"Calling get_article_title_url_list with query: {query}")
    search_results = web_searcher.search(query, num_results=5)
    results_list = []
    for result in search_results:
        results_list.append({"title": result["title"], "url": result["url"]})
    return json.dumps(results_list, ensure_ascii=False)


def get_article_from_title_url(
    content_fetcher: ArticleContentFetcher,
    article_cleaner: ArticleCleaner,
    summary_generator: ArticleSummaryGenerator,
    article_collection,
    title: str,
    url: str,
) -> str:
    print(f"Calling create_article_from_title_url with query: {title}")
    try:
        raw_content = content_fetcher.fetch(url)
        if not raw_content:
            return f"No content fetched from {url}."

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

        formatted_article = (
            f"title: {title}\n"
            f"url: {url}\n"
            f"summary: {summary}\n"
        )
        return formatted_article

    except Exception as e:
        print(f"Failed to process article at {url}: {e}")
        return f"Failed to process article at {url}: {str(e)}"
