import os
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from openai import OpenAI
from rss_article_uploader import RssArticleUploader
from article import Article
from article_cleaner import ArticleCleaner
from static_news_generator import StaticNewsGenerator
from user import User
from question import Question, ANSWER_STATUS
from answer_agent import AnswerAgent
from web_searcher import WebSearcher
from news_generation_agent import NewsGenerationAgent

# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# OpenAI 初期化
client = OpenAI()

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

    web_searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)
    generator = NewsGenerationAgent(db=db, web_searcher=web_searcher)
    for language_code in ["ja", "en"]:
        news = generator.create(language_code)
        print(f"[INFO] Created news - {language_code}: {news.content}")

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


@functions_framework.cloud_event
def on_question_created(cloud_event: CloudEvent) -> None:
    """
    questionsコレクションに新規ドキュメントが追加された時に実行
    """
    print(f"Triggered by creation of a document: {cloud_event['source']}")

    doc_event_data = firestore_event.DocumentEventData()
    doc_event_data._pb.ParseFromString(cloud_event.data)

    doc_path = doc_event_data.value.name
    user_id = doc_path.split("/")[-1]
    print(f"user_id: {user_id}")

    question_ref = Question.collection(db)
    question = Question.get(question_ref, user_id)

    user_ref = User.collection(db)
    user = User.get(user_ref, user_id)

    if user.daily_usage_count >= 4:
        print(
            f"[INFO] Skip Question answer creation : daily_usage_count - {user.daily_usage_count}"
        )
        return

    agent_answer = ""
    try:
        answer_agent = AnswerAgent(db=db)
        agent_answer = answer_agent.answer(
            user_id=user_id, question=question.question_text
        )
        question.answer_text = agent_answer
        question.answer_status = ANSWER_STATUS["READY"]
        question.update(question_ref)
    except Exception as e:
        question.answer_text = ""
        question.answer_status = ANSWER_STATUS["ERROR"]
        question.update(question_ref)
        print(f"[ERROR] Unexpected error: {e}")
        return

    user.add_conversation(
        db=db,
        user_message=question.question_text,
        agent_message=agent_answer,
    )

    print(f"[INFO] Question answer creation success: {agent_answer}")
