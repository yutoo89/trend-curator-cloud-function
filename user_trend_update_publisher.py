import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta, timezone
from google.cloud import pubsub_v1
import json


class UserTrendUpdatePublisher:
    def __init__(self, batch_size: int = 1000):
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        self.db = firestore.client()
        self.publisher = pubsub_v1.PublisherClient()
        self.batch_size = batch_size

    def is_recent_access(self, last_accessed: datetime, one_week_ago: datetime) -> bool:
        """
        Checks if the last accessed time is within the past week.
        """
        return last_accessed >= one_week_ago

    def is_within_access_interval(
        self, last_accessed: datetime, previous_accessed: datetime
    ) -> bool:
        """
        Checks if the last accessed time is within the access interval (difference between last and previous accessed times).
        """
        access_interval = last_accessed - previous_accessed
        return last_accessed <= previous_accessed + access_interval

    def publish(self, user_id: str):
        """
        Publishes a message to Pub/Sub for a given user ID.
        """
        message_data = {"user_id": user_id}
        self.publisher.publish(
            "projects/trend-curator/topics/user-trend-updates",
            data=json.dumps(message_data).encode("utf-8"),
        )
        self.published_user_count += 1
        print(f"[INFO] Message sent for user: {user_id}")

    def fetch_and_publish(self):
        print(f"[INFO] Publishing user-trend-update - Start")
        collection_ref = self.db.collection("accesses")
        query = collection_ref.limit(self.batch_size)
        last_doc = None
        one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)
        self.published_user_count = 0

        while True:
            if last_doc:
                query = query.start_after(last_doc)

            docs = query.get()
            if not docs:
                break

            for doc in docs:
                try:
                    data = doc.to_dict()
                    user_id = doc.id
                    last_accessed = data.get("last_accessed")
                    previous_accessed = data.get("previous_accessed")

                    if not last_accessed and not previous_accessed:
                        print(
                            f"[DEBUG] Skipping user {user_id}: Missing both timestamps."
                        )
                        continue

                    if last_accessed:
                        last_accessed_dt = datetime.fromisoformat(
                            last_accessed.replace("Z", "+00:00")
                        )

                        # Check if recent access
                        if self.is_recent_access(last_accessed_dt, one_week_ago):
                            self.publish(user_id)
                            continue

                        # Check if within access interval
                        if previous_accessed:
                            previous_accessed_dt = datetime.fromisoformat(
                                previous_accessed.replace("Z", "+00:00")
                            )
                            if self.is_within_access_interval(
                                last_accessed_dt, previous_accessed_dt
                            ):
                                self.publish(user_id)
                                continue

                except Exception as e:
                    print(f"[ERROR] Failed to process document {doc.id}: {e}")

            last_doc = docs[-1]
            if len(docs) < self.batch_size:
                break

        print(
            f"[INFO] Publishing user-trend-update - Done. Published user count: {self.published_user_count}"
        )
        return self.published_user_count
