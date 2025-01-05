from __future__ import annotations
from firebase_admin import firestore
from gemini_text_corrector import GeminiTextCorrector

class Topic:
    def __init__(self, user_id: str, raw_topic: str, topic: str, language_code: str, region_code: str):
        self.user_id = user_id
        self.raw_topic = raw_topic
        self.topic = topic
        self.language_code = language_code
        self.region_code = region_code

    @staticmethod
    def update(db: firestore.Client, user_id: str, raw_topic: str, locale: str) -> Topic:
        parts = locale.split('-')
        if len(parts) != 2:
            raise ValueError("Invalid locale format. Expected format: 'language-region'.")
        language_code, region_code = parts

        corrector = GeminiTextCorrector("gemini-1.5-flash")
        corrected_topic = corrector.run(raw_topic, region_code)

        doc_ref = db.collection("topics").document(user_id)
        doc_ref.update({
            "topic": corrected_topic,
            "language_code": language_code,
            "region_code": region_code,
        })

        return Topic(user_id, raw_topic, corrected_topic, language_code, region_code)
