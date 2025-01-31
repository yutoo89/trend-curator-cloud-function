import uuid
from datetime import datetime
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class News:
    COLLECTION = "news"

    def __init__(
        self,
        content: str,
        sample_question: str,
        keyword: str,
        language_code: str,
        published: datetime = None,
        id: str = None,
    ):
        self.id = id if id else str(uuid.uuid4())
        self.content = content
        self.sample_question = sample_question
        self.keyword = keyword
        self.language_code = language_code
        self.published = published if published else datetime.now()

    @staticmethod
    def from_dict(source):
        return News(
            id=source.get("id"),
            content=source.get("content", ""),
            sample_question=source.get("sample_question", ""),
            keyword=source.get("keyword", ""),
            language_code=source.get("language_code", ""),
            published=source.get("published", datetime.now()),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "sample_question": self.sample_question,
            "keyword": self.keyword,
            "language_code": self.language_code,
            "published": self.published,
        }

    def save(self, ref):
        doc_ref = ref.document(self.id)
        doc_ref.set(self.to_dict())

    @staticmethod
    def get_collection(db: firestore.Client):
        return db.collection(News.COLLECTION)

    @staticmethod
    def get_recent_news(db: firestore.Client, language_code: str) -> str:
        collection_ref = News.get_collection(db)
        query = (
            collection_ref.where(
                filter=FieldFilter("language_code", "==", language_code)
            )
            .order_by("published", direction="DESCENDING")
            .limit(3)
        )

        docs = query.stream()
        result_strings = []

        for doc in docs:
            news_dict = doc.to_dict()
            published_date = news_dict.get("published", datetime.now()).strftime(
                "%Y-%m-%d %H:%M UTC"
            )
            content = news_dict.get("content", "")
            result_strings.append(f"{published_date}\n{content}")

        return "\n\n".join(result_strings)

    @staticmethod
    def get_latest_news(db: firestore.Client, language_code: str) -> "News":
        """
        指定した言語の最新ニュースを1件取得してNewsインスタンスを返す
        """
        collection_ref = News.get_collection(db)
        query = (
            collection_ref.where(
                filter=FieldFilter("language_code", "==", language_code)
            )
            .order_by("published", direction="DESCENDING")
            .limit(1)
        )
        docs = query.stream()
        for doc in docs:
            return News.from_dict(doc.to_dict())
        return None
