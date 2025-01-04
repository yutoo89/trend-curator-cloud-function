from firebase_admin import firestore
from gemini_trend_curator import GeminiTrendCurator


class TrendUpdater:
    def __init__(self, db: firestore.Client, user_id: str, topic: str):
        self.db = db
        self.user_id = user_id
        self.topic = topic
        self.curator = GeminiTrendCurator("gemini-1.5-flash")

    def run(self) -> None:
        doc_ref = self.db.collection("trends").document(self.user_id)
        digests = self.curator.run(self.topic)
        doc_ref.set(
            {
                "topic": self.topic,
                "supplementary_topic": None,
                "digests": digests,
            },
            merge=True,
        )
