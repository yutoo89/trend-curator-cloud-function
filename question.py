from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore import CollectionReference

ANSWER_STATUS = {
    "NO_QUESTION": "質問なし",
    "IN_PROGRESS": "回答作成中",
    "READY": "回答作成済み",
    "ANSWERED": "回答済み",
    "ERROR": "エラー",
}


class Question:
    COLLECTION = "questions"

    def __init__(
        self,
        user_id: str,
        question_text: str,
        answer_text: str = "",
        answer_status: str = ANSWER_STATUS["IN_PROGRESS"],
        created: datetime = None,
    ):
        self.user_id = user_id
        self.question_text = question_text
        self.answer_text = answer_text
        self.answer_status = answer_status
        self.created = created if created else datetime.now()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "question_text": self.question_text,
            "answer_text": self.answer_text,
            "answer_status": self.answer_status,
            "created": self.created,
        }

    @staticmethod
    def from_dict(source: dict) -> "Question":
        if not source:
            return None
        return Question(
            user_id=source.get("user_id"),
            question_text=source.get("question_text"),
            answer_text=source.get("answer_text", ""),
            answer_status=source.get("answer_status", ANSWER_STATUS["IN_PROGRESS"]),
            created=source.get("created", datetime.now()),
        )

    @staticmethod
    def collection(db: firestore.Client):
        return db.collection(Question.COLLECTION)

    def delete(self, ref: CollectionReference):
        ref.document(self.user_id).delete()

    def save(self, ref: CollectionReference):
        doc_ref = ref.document(self.user_id)
        doc_ref.set(self.to_dict())

    @staticmethod
    def get(ref: CollectionReference, user_id: str) -> "Question":
        doc = ref.document(user_id).get()
        if doc.exists:
            return Question.from_dict(doc.to_dict())
        return None

    def update(self, ref: CollectionReference) -> bool:
        doc_ref = ref.document(self.user_id)
        if doc_ref.get().exists:
            doc_ref.update(self.to_dict())
            return True
        return False
