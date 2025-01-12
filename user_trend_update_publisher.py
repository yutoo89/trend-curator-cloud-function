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

    def fetch_and_publish(self):
        """
        Fetches user access records and returns a list of user IDs requiring an update.
        """
        collection_ref = self.db.collection("accesses")
        query = collection_ref.limit(self.batch_size)  # Initial batch query
        last_doc = None  # Track the last document processed
        one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)
        published_user_count = 0

        while True:
            if last_doc:
                query = query.start_after(last_doc)

            docs = query.get()
            if not docs:
                break  # Exit if no documents remain

            for doc in docs:
                data = doc.to_dict()
                last_accessed = data.get("last_accessed")
                previous_accessed = data.get("previous_accessed")
                print(f"last:{last_accessed}")
                print(f"prev:{previous_accessed}")

                if last_accessed and previous_accessed:
                    # Convert timestamps to datetime objects
                    last_accessed_dt = datetime.fromisoformat(
                        last_accessed.replace("Z", "+00:00")
                    )
                    previous_accessed_dt = datetime.fromisoformat(
                        previous_accessed.replace("Z", "+00:00")
                    )

                    # Check conditions
                    print(
                        f"chack a:{self.is_recent_access(last_accessed_dt, one_week_ago)}"
                    )
                    print(
                        f"chack b:{self.is_within_access_interval(last_accessed_dt, previous_accessed_dt)}"
                    )
                    if self.is_recent_access(
                        last_accessed_dt, one_week_ago
                    ) or self.is_within_access_interval(
                        last_accessed_dt, previous_accessed_dt
                    ):
                        user_id = doc.id
                        print(f"Processing user: {user_id}")

                        # メッセージ作成
                        message_data = {
                            "user_id": user_id,
                        }
                        # メッセージをPub/Subに送信
                        self.publisher.publish(
                            "projects/trend-curator/topics/user-trend-updates",
                            data=json.dumps(message_data).encode("utf-8"),
                        )
                        published_user_count += 1
                        print(f"Message sent for user: {user_id}")

                else:
                    print(
                        f"Document ID: {doc.id} has missing 'last_accessed' or 'previous_accessed' fields."
                    )

            # Update last_doc for next batch
            last_doc = docs[-1]

            if len(docs) < self.batch_size:
                break

        return published_user_count
