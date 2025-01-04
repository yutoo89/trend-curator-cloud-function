from datetime import datetime, timezone
from firebase_admin import firestore


class AccessUpdater:
    def __init__(self, db: firestore.Client, user_id: str):
        self.db = db
        self.user_id = user_id

    def run(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = self.db.collection("accesses").document(self.user_id)
        doc = doc_ref.get()

        if doc.exists:
            access_data = doc.to_dict()
            current_last_accessed = access_data.get("last_accessed")

            doc_ref.set(
                {"last_accessed": now, "previous_accessed": current_last_accessed},
                merge=True,
            )
        else:
            doc_ref.set({"last_accessed": now, "previous_accessed": None})
