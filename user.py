from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud.firestore import CollectionReference
from google.cloud.firestore_v1.base_query import FieldFilter
from conversation_record import ConversationRecord
from question import Question, ANSWER_STATUS

LANGUAGE_CODE = {
    "EN": "en",
    "JA": "ja",
}


class User:
    COLLECTION = "users"

    def __init__(
        self,
        id: str,
        language_code: str,
        daily_usage_count: int = 0,
        last_question_date: datetime = None,
    ):
        self.id = id
        self.language_code = language_code
        self.daily_usage_count = daily_usage_count
        self.last_question_date = (
            last_question_date if last_question_date else datetime.now()
        )

    @staticmethod
    def from_dict(source):
        return User(
            id=source.get("id"),
            daily_usage_count=source.get("daily_usage_count", 0),
            last_question_date=source.get("last_question_date", datetime.now()),
            language_code=source.get("language_code"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "daily_usage_count": self.daily_usage_count,
            "last_question_date": self.last_question_date,
            "language_code": self.language_code,
        }

    def save(self, ref: CollectionReference):
        doc_ref = ref.document(self.id)
        doc_ref.set(self.to_dict())

    def update(self, ref: CollectionReference, updates):
        doc_ref = ref.document(self.id)
        doc_ref.update(updates)

    @staticmethod
    def get(ref: CollectionReference, id: str) -> "User":
        doc = ref.document(id).get()
        if doc.exists:
            data = doc.to_dict()
            user = User.from_dict(data)
            user = user.reset_usage_count(ref)
            return user
        else:
            return None

    @staticmethod
    def get_or_create(
        ref: CollectionReference, user_id: str, language_code: str
    ) -> "User":
        user = User.get(ref, user_id)
        if not user:
            user = User(user_id, language_code=language_code)
            user.save(ref)
        return user

    @staticmethod
    def collection(db):
        return db.collection(User.COLLECTION)

    @staticmethod
    def exists(ref: CollectionReference, id: str) -> bool:
        doc_ref = ref.document(id)
        return doc_ref.get().exists

    def reset_usage_count(self, ref: CollectionReference) -> "User":
        now = datetime.now()
        if self.last_question_date.date() != now.date():
            self.daily_usage_count = 0
            self.last_question_date = now
            self.save(ref)
        return self

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

        user_record = ConversationRecord(self.id, "user", user_message, user_timestamp)
        agent_record = ConversationRecord(
            self.id, "agent", agent_message, agent_timestamp
        )

        ref.document(user_record.id).set(user_record.to_dict())
        ref.document(agent_record.id).set(agent_record.to_dict())

    def recreate_question(
        self,
        db: firestore.Client,
        question_text: str,
        answer_status: str = ANSWER_STATUS["IN_PROGRESS"],
    ):
        question_ref = Question.collection(db)

        existing_question = Question.get(question_ref, self.id)
        if existing_question:
            existing_question.delete(question_ref)

        question = Question(
            user_id=self.id,
            question_text=question_text,
            answer_text="",
            answer_status=answer_status,
        )
        question.save(question_ref)
        return question

    def get_question(self, db) -> Question:
        if hasattr(self, "_cached_question"):
            return self._cached_question
        doc = Question.collection(db).document(self.id).get()
        data = doc.to_dict()
        self._cached_question = Question.from_dict(data) if data else None
        return self._cached_question

    def get_answer_status(self, db) -> str:
        if hasattr(self, "_cached_answer_status"):
            return self._cached_answer_status
        question = self.get_question(db)
        if not question:
            self._cached_answer_status = ANSWER_STATUS["NO_QUESTION"]
        else:
            self._cached_answer_status = question.answer_status
        return self._cached_answer_status
