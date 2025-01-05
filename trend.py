from __future__ import annotations
from firebase_admin import firestore
from gemini_trend_curator import GeminiTrendCurator

class Trend:
    def __init__(self, user_id: str, topic: str, digests: list):
        self.user_id = user_id
        self.topic = topic
        self.digests = digests

    @staticmethod
    def update(db: firestore.Client, user_id: str, topic: str, language_code: str, region_code: str) -> Trend:
        curator = GeminiTrendCurator("gemini-1.5-flash")
        digests = curator.run(topic, language_code, region_code)

        doc_ref = db.collection("trends").document(user_id)
        doc_ref.set(
            {
                "topic": topic,
                "supplementary_topic": None,
                "digests": digests,
            },
            merge=True,
        )

        return Trend(user_id, topic, digests)
