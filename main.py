import os
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from topic import Topic
from news import News
from news_topic_selector import NewsTopicSelector
from access_updater import AccessUpdater
from web_searcher import WebSearcher
from user_trend_update_publisher import UserTrendUpdatePublisher
from rss_article_uploader import RssArticleUploader
from article import Article
import base64
import json
from article_cleaner import ArticleCleaner

# TODO:
# - ベクトル保存処理をfirestoreに置き換え
# - RAGの回答生成処理をfirestoreに置き換え

# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# Firestore 初期化
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

# Google Custom Search
google_custom_search_api_key = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
google_search_cse_id = os.environ["GOOGLE_SEARCH_CSE_ID"]


@functions_framework.cloud_event
def on_topic_created(cloud_event: CloudEvent) -> None:
    """
    topicsコレクションに新規ドキュメントが追加された時に実行
    """
    print(f"Triggered by creation of a document: {cloud_event['source']}")

    doc_event_data = firestore_event.DocumentEventData()
    doc_event_data._pb.ParseFromString(cloud_event.data)

    doc_path = (
        doc_event_data.value.name
    )  # "projects/<PROJ>/databases/(default)/documents/topics/<user_id>"
    user_id = doc_path.split("/")[-1]

    if "raw_topic" not in doc_event_data.value.fields:
        print(f"No 'raw_topic' field found in document: {user_id}")
        return

    # 1. topic取得
    topic = Topic.get(db, user_id)
    if not topic.is_technical_term:
        print(
            f"[INFO] Topic '{topic.topic}' is not a technical term. Execution stopped for user {user_id}."
        )
        return

    # 2. accessessを更新
    AccessUpdater(db, user_id).run()

    # 3. newsを更新
    news = News.create(db, user_id, topic.topic, topic.language_code)
    if not news.increment_usage():
        print(
            f"[INFO] User {user_id} has exceeded their monthly usage limit. Stopping execution."
        )
        return
    searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)
    selector = NewsTopicSelector("gemini-1.5-flash", searcher)
    news.update(selector)


@functions_framework.cloud_event
def on_trend_update_started(cloud_event):
    """
    trend-updatesトピックにメッセージが送信された時に実行
    """
    # TODO: RAG Agentを使った実装に置き換えたら下記は削除
    # UserTrendUpdatePublisher().fetch_and_publish()

    uploader = RssArticleUploader("gemini-1.5-flash", db)
    uploader.bulk_upload()


@functions_framework.cloud_event
def on_user_trend_update_started(cloud_event):
    """
    user-trend-updatesトピックにメッセージが送信された時に実行
    """

    print(f"[INFO] Processing on_user_trend_update_started - Start")
    pubsub_message = cloud_event.data

    if "message" not in pubsub_message or "data" not in pubsub_message["message"]:
        print("Invalid Pub/Sub message format.")
        return

    message_data = base64.b64decode(pubsub_message["message"]["data"]).decode("utf-8")
    message_json = json.loads(message_data)
    user_id = message_json.get("user_id", None)

    if not user_id:
        print("No user_id found in message.")
        return

    # ニュースを更新
    searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)
    selector = NewsTopicSelector("gemini-1.5-flash", searcher)
    news = News.get(db, user_id)
    news.update(selector)


@functions_framework.cloud_event
def on_article_created(cloud_event: CloudEvent) -> None:
    """
    articlesコレクションに新規ドキュメントが追加された時に実行
    """
    print(f"Triggered by creation of a document: {cloud_event['source']}")

    doc_event_data = firestore_event.DocumentEventData()
    doc_event_data._pb.ParseFromString(cloud_event.data)

    doc_path = doc_event_data.value.name
    doc_id = doc_path.split("/")[-1]

    article_collection = Article.collection(db)
    article = Article.get(article_collection, doc_id)

    article.import_body(article_collection, ArticleCleaner("gemini-1.5-flash"))
    article.vectorize(article_collection)

    print(f"[INFO] Article vectorize success: {article.title}")
