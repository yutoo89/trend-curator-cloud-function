from datetime import datetime, timedelta
import uuid
from enum import Enum
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from conversation_record import ConversationRecord


class AnswerStatus(Enum):
    NO_QUESTION = "質問なし"
    IN_PROGRESS = "回答作成中"
    ANSWERED = "回答あり"


class LanguageCode(Enum):
    EN = "en"
    JA = "ja"


class Role(Enum):
    USER = "user"
    AGENT = "agent"


class User:
    COLLECTION = "users"

    def __init__(
        self,
        answer_status: AnswerStatus = AnswerStatus.NO_QUESTION,
        answer_text: str = "",
        daily_usage_count: int = 0,
        last_question_date: datetime = None,
        language_code: LanguageCode = LanguageCode.JA,
        id: str = None,
    ):
        self.id = id if id else str(uuid.uuid4())
        self.answer_status = answer_status
        self.answer_text = answer_text
        self.daily_usage_count = daily_usage_count
        self.last_question_date = (
            last_question_date if last_question_date else datetime.now()
        )
        self.language_code = language_code

    @staticmethod
    def from_dict(source):
        return User(
            id=source.get("id"),
            answer_status=AnswerStatus(
                source.get("answer_status", AnswerStatus.NO_QUESTION.value)
            ),
            answer_text=source.get("answer_text", ""),
            daily_usage_count=source.get("daily_usage_count", 0),
            last_question_date=source.get("last_question_date", datetime.now()),
            language_code=LanguageCode(
                source.get("language_code", LanguageCode.JA.value)
            ),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "answer_status": self.answer_status.value,
            "answer_text": self.answer_text,
            "daily_usage_count": self.daily_usage_count,
            "last_question_date": self.last_question_date,
            "language_code": self.language_code.value,
        }

    def save(self, ref):
        doc_ref = ref.document(self.id)
        doc_ref.set(self.to_dict())

    def update(self, ref, updates):
        doc_ref = ref.document(self.id)
        doc_ref.update(updates)

    @staticmethod
    def get(ref, id):
        doc = ref.document(id).get()
        if doc.exists:
            data = doc.to_dict()
            return User.from_dict(data)
        else:
            return None

    @staticmethod
    def collection(db):
        return db.collection(User.COLLECTION)

    @staticmethod
    def exists(ref, id):
        doc_ref = ref.document(id)
        return doc_ref.get().exists

    def today_usage_count(self, db):
        now = datetime.now()
        if self.last_question_date.date() != now.date():
            self.daily_usage_count = 0
            self.last_question_date = now
            self.save(User.collection(db))
        return self.daily_usage_count

    def conversations(self, db):
        since = datetime.now() - timedelta(hours=24)
        ref = db.collection("users").document(self.id).collection("conversations")
        query = ref.where(filter=FieldFilter("timestamp", ">=", since))
        docs = query.stream()
        return [ConversationRecord.from_dict(doc.to_dict()) for doc in docs]

    def format_conversations(self, db):
        formatted = [
            f"{conv.timestamp.strftime('%Y-%m-%d %H:%M')} - {conv.role}: {conv.message}"
            for conv in sorted(self.conversations(db), key=lambda x: x.timestamp)
        ]
        return "\n".join(formatted)

    def add_conversation(self, db, user_message: str, agent_message: str):
        now = datetime.now()
        ref = db.collection("users").document(self.id).collection("conversations")

        user_timestamp = now - timedelta(seconds=10)
        agent_timestamp = now

        user_record = ConversationRecord(
            self.id, Role.USER.value, user_message, user_timestamp
        )
        agent_record = ConversationRecord(
            self.id, Role.AGENT.value, agent_message, agent_timestamp
        )

        ref.document(user_record.id).set(user_record.to_dict())
        ref.document(agent_record.id).set(agent_record.to_dict())

        if self.last_question_date.date() != now.date():
            self.daily_usage_count = 1
        else:
            self.daily_usage_count += 1

        self.last_question_date = now
        self.save(User.collection(db))


# import os
# import firebase_admin
# from firebase_admin import firestore

# # Firestore 初期化
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# # Google Custom Search
# google_custom_search_api_key = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
# google_search_cse_id = os.environ["GOOGLE_SEARCH_CSE_ID"]

# db = firestore.Client()
# user_id = "test_user"
# user_ref = User.collection(db)

# # ユーザーを取得または新規作成
# user = User.get(user_ref, user_id)
# if not user:
#     user = User(id=user_id)
#     user.save(user_ref)

# # 1. today_usage_countのテスト
# usage_count = user.today_usage_count(db)
# print(f"Usage Count: {usage_count}")

# # 2. add_conversationのテスト
# user.add_conversation(db, "わーい", "あなたはすごいです。頑張りました！")
# print("Added a new conversation.")

# # 3. conversationsのテスト
# recent_conversations = user.format_conversations(db)
# print("Recent Conversations:\n", recent_conversations)

# usage_count = user.today_usage_count(db)
# print(f"Usage Count: {usage_count}")

# print(user.last_question_date.date())
# print(user.language_code)
