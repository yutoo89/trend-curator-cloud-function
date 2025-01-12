import os
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from topic import Topic
from trend import Trend
from access_updater import AccessUpdater
from web_searcher import WebSearcher

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

    # 1. raw_topicをLLMで整形してtopicに書き込む
    raw_topic = doc_event_data.value.fields["raw_topic"].string_value
    locale = doc_event_data.value.fields["locale"].string_value
    topic = Topic.update(db, user_id, raw_topic, locale)

    # 2. accessessを更新
    AccessUpdater(db, user_id).run()

    # 3. trendsを更新
    exclude_keywords = []
    if "exclude_keywords" in doc_event_data.value.fields:
        exclude_keywords = [
            kw.string_value
            for kw in doc_event_data.value.fields["exclude_keywords"].array_value.values
        ]

    searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)
    trend = Trend.update(
        db,
        user_id,
        topic.topic,
        topic.language_code,
        searcher,
        exclude_keywords,
    )
    Topic.update_exclude_keywords(db, user_id, trend.keywords)
    print(f"Trend updated for user: {user_id}")


@functions_framework.cloud_event
def on_trend_update_started(cloud_event):
    from user_trend_update_publisher import UserTrendUpdatePublisher
    print(f"[INFO] Publishing user-trend-update - Start")
    published_user_count = UserTrendUpdatePublisher().fetch_and_publish()
    print(f"[INFO] Publishing user-trend-update - Done\npublished_user_count: {published_user_count}")


@functions_framework.cloud_event
def on_user_trend_update_started(cloud_event):
    """
    「ユーザトレンドの更新が開始したとき」に実行。
    メッセージに含まれるユーザIDを基にニュースを作成。
    """
    import base64

    # CloudEventデータを取得
    pubsub_message = cloud_event.data
    if "message" in pubsub_message and "data" in pubsub_message["message"]:
        # メッセージデータをデコード
        message_data = base64.b64decode(pubsub_message["message"]["data"]).decode("utf-8")
        print(f"Received message: {message_data}")
        
        # ユーザIDを取得
        import json
        message_json = json.loads(message_data)
        user_id = message_json.get("user_id", None)
        if user_id:
            print(f"Generating news for user: {user_id}")
        else:
            print("No user_id found in message.")
    else:
        print("Invalid Pub/Sub message format.")
