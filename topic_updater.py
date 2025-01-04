from firebase_admin import firestore
from gemini_text_corrector import GeminiTextCorrector


class TopicUpdater:
    def __init__(self, db: firestore.Client, user_id: str, raw_topic: str):
        self.db = db
        self.user_id = user_id
        self.raw_topic = raw_topic
        self.corrector = GeminiTextCorrector("gemini-1.5-flash")

    def run(self) -> None:
        topic = self.corrector.run(self.raw_topic)
        doc_ref = self.db.collection("topics").document(self.user_id)
        doc_ref.update({"topic": topic})
