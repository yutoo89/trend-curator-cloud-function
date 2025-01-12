from __future__ import annotations
from firebase_admin import firestore
from gemini_text_corrector import GeminiTextCorrector


class Topic:
    def __init__(
        self,
        user_id: str,
        raw_topic: str,
        topic: str,
        language_code: str,
        region_code: str,
        exclude_keywords: list[str] = None,
    ):
        if exclude_keywords is None:
            exclude_keywords = []
        self.user_id = user_id
        self.raw_topic = raw_topic
        self.topic = topic
        self.language_code = language_code
        self.region_code = region_code
        self.exclude_keywords = exclude_keywords

    @staticmethod
    def find(db: firestore.Client, user_id: str) -> Topic:
        topic_data = db.collection("topics").document(user_id).get().to_dict()
        return Topic(
            user_id,
            topic_data.get("raw_topic"),
            topic_data.get("topic"),
            topic_data.get("language_code"),
            topic_data.get("region_code"),
            topic_data.get("exclude_keywords"),
        )

    @staticmethod
    def update(
        db: firestore.Client, user_id: str, raw_topic: str, locale: str
    ) -> Topic:
        parts = locale.split("-")
        if len(parts) != 2:
            raise ValueError(
                "Invalid locale format. Expected format: 'language-region'."
            )
        language_code, region_code = parts

        corrector = GeminiTextCorrector("gemini-1.5-flash")
        corrected_topic = corrector.run(raw_topic, region_code)

        doc_ref = db.collection("topics").document(user_id)
        doc_ref.update(
            {
                "topic": corrected_topic,
                "language_code": language_code,
                "region_code": region_code,
            }
        )

        return Topic(user_id, raw_topic, corrected_topic, language_code, region_code)

    @staticmethod
    def update_exclude_keywords(
        db: firestore.Client, user_id: str, exclude_keywords: list[str]
    ) -> None:
        if not isinstance(exclude_keywords, list) or not all(
            isinstance(k, str) for k in exclude_keywords
        ):
            raise ValueError("exclude_keywords must be a list of strings.")

        doc_ref = db.collection("topics").document(user_id)
        doc_ref.update(
            {
                "exclude_keywords": exclude_keywords,
            }
        )
