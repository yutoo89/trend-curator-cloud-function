from datetime import datetime, timezone
from firebase_admin import firestore
from trend import Trend


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

            if current_last_accessed:
                last_accessed_date = datetime.fromisoformat(current_last_accessed)
                if (
                    last_accessed_date.month != datetime.now().month
                    or last_accessed_date.year != datetime.now().year
                ):
                    Trend.reset_usage(self.db, self.user_id)

            doc_ref.set(
                {"last_accessed": now, "previous_accessed": current_last_accessed},
                merge=True,
            )
        else:
            doc_ref.set({"last_accessed": now, "previous_accessed": None})
