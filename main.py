import os
import json
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from topic_updater import TopicUpdater
from trend_updater import TrendUpdater
from access_updater import AccessUpdater

# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# Firestore 初期化
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()


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
    topic = TopicUpdater(db, user_id, raw_topic).run()

    # 2. accessessを更新
    AccessUpdater(db, user_id).run()

    # 3. trendsを更新
    TrendUpdater(db, user_id, topic).run()
    print(f"Trend updated for user: {user_id}")
