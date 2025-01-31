from datetime import datetime
from google.cloud import firestore

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
        answer_status: str = ANSWER_STATUS["NO_QUESTION"],
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
            answer_status=source.get("answer_status", ANSWER_STATUS["NO_QUESTION"]),
            created=source.get("created", datetime.now()),
        )

    @staticmethod
    def collection(db: firestore.Client):
        return db.collection(Question.COLLECTION)

    def save(self, db: firestore.Client):
        doc_ref = Question.collection(db).document(self.user_id)
        doc_ref.set(self.to_dict())

    @staticmethod
    def get(db: firestore.Client, user_id: str) -> "Question":
        doc = Question.collection(db).document(user_id).get()
        if doc.exists:
            return Question.from_dict(doc.to_dict())
        return None

    @staticmethod
    def create(db: firestore.Client, user_id: str, question_text: str) -> "Question":

        question = Question(user_id=user_id, question_text=question_text)
        question.save(db)
        return question
