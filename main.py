import os
import json
from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from datetime import datetime, timezone
from corrector import GeminiTextCorrector

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
    1. raw_topicをLLMで整形してtopicに書き込む
    """
    print(f"Triggered by creation of a document: {cloud_event['source']}")

    doc_event_data = firestore_event.DocumentEventData()
    doc_event_data._pb.ParseFromString(cloud_event.data)

    doc_path = (
        doc_event_data.value.name
    )  # "projects/<PROJ>/databases/(default)/documents/topics/<user_id>"
    user_id = doc_path.split("/")[-1]

    if "raw_topic" in doc_event_data.value.fields:
        raw_topic = doc_event_data.value.fields["raw_topic"].string_value
        corrector = GeminiTextCorrector("gemini-1.5-flash")
        topic = corrector.run(raw_topic)

        print(f"user_id: {user_id}, raw_topic: {raw_topic} => topic: {topic}")

        doc_ref = db.collection("topics").document(user_id)
        doc_ref.update({"topic": topic})
    else:
        print(f"No 'raw_topic' field found in document: {user_id}")
