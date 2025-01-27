import os
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from rss_article_uploader import RssArticleUploader
from article import Article
from article_cleaner import ArticleCleaner
from static_news_generator import StaticNewsGenerator

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
def on_trend_update_started(cloud_event):
    """
    trend-updatesトピックにメッセージが送信された時に実行
    """
    uploader = RssArticleUploader("gemini-1.5-flash", db)
    uploader.bulk_upload()

    generator = StaticNewsGenerator(db, "gemini-1.5-flash")
    for language_code in ["ja", "en"]:
        static_news = generator.generate_news(language_code)
        print(f"[INFO] Created static news: {static_news.body}")


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

