from cloudevents.http import CloudEvent
import functions_framework
from google.events.cloud import firestore as firestore_event
import firebase_admin
from firebase_admin import credentials, firestore
import os
import google.generativeai as genai
import typing_extensions as typing
import json
from datetime import datetime, timezone


print("initialize GenAI client")
genai.configure(api_key=os.environ["GENAI_API_KEY"])

print("No explicit SERVICE_ACCOUNT_KEY is used. We'll rely on default credentials.")

if not firebase_admin._apps:
    print("initialize_app with default credentials")
    firebase_admin.initialize_app()

print("initialize firestore client")
db = firestore.client()


class CorrectorResult(typing.TypedDict):
    original_text: str
    transformed_text: str


class GeminiTextCorrector:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, input_text: str) -> str:
        lines = [
            f"音声認識で「{input_text}」というテキストが得られました。",
            "このテキストは誤字や欠損がある可能性があるので、元の単語を推測して広く知られる正しい表記に変換してください。",
            "テキストに誤りがない場合はそのままの形で出力してください。",
            "例:",
            "- input: `生成 エーアイ`",
            "- output: `生成AI`",
        ]
        return "\n".join(lines)

    def run(self, input_text: str) -> str:
        prompt = self.create_prompt(input_text)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[CorrectorResult],
            ),
        )

        return json.loads(response.text)[0]["transformed_text"]


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
