from __future__ import annotations
from firebase_admin import firestore
from gemini_text_corrector import GeminiTextCorrector


class DocumentNotFoundError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class Topic:
    COLLECTION_NAME = "topics"

    def __init__(
        self,
        user_id: str,
        raw_topic: str,
        topic: str,
        language_code: str,
        region_code: str,
        reading: str,
        is_technical_term: bool,
        exclude_keywords: list[str] = None,
        queries: list[str] = None,
    ):
        if exclude_keywords is None:
            exclude_keywords = []
        if queries is None:
            queries = []
        self.user_id = user_id
        self.raw_topic = raw_topic
        self.topic = topic
        self.language_code = language_code
        self.region_code = region_code
        self.reading = reading
        self.is_technical_term = is_technical_term
        self.exclude_keywords = exclude_keywords
        self.queries = queries
        self.locale = f"{language_code}-{region_code}"

    @staticmethod
    def get(db: firestore.Client, user_id: str) -> Topic:
        doc = db.collection(Topic.COLLECTION_NAME).document(user_id).get()

        if not doc.exists:
            raise DocumentNotFoundError(
                f"Document with user_id '{user_id}' not found in collection '{Topic.COLLECTION_NAME}'."
            )

        doc_data = doc.to_dict()

        raw_topic = doc_data.get("raw_topic")
        topic = doc_data.get("topic")
        reading = doc_data.get("reading")
        is_technical_term = doc_data.get("is_technical_term", False)
        language_code = doc_data.get("language_code")
        region_code = doc_data.get("region_code")
        exclude_keywords = doc_data.get("exclude_keywords", [])
        queries = doc_data.get("queries", [])

        return Topic(
            user_id=user_id,
            raw_topic=raw_topic,
            topic=topic,
            language_code=language_code,
            region_code=region_code,
            reading=reading,
            is_technical_term=is_technical_term,
            exclude_keywords=exclude_keywords,
            queries=queries,
        )
