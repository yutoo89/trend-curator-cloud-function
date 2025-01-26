import uuid
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter


class ConversationRecord:
    COLLECTION = "conversations"

    def __init__(
        self,
        user_id: str,
        role: str,
        message: str,
        timestamp: datetime = None,
        id: str = None,
    ):
        self.id = id if id else str(uuid.uuid4())
        self.user_id = user_id
        self.role = role  # "user" or "agent"
        self.message = message
        self.timestamp = timestamp if timestamp else datetime.now()

    @staticmethod
    def from_dict(source: dict):
        """
        Firestore ドキュメントから取得した dict を ConversationRecord インスタンスに変換します。
        """
        return ConversationRecord(
            id=source.get("id"),
            user_id=source.get("user_id"),
            role=source.get("role"),
            message=source.get("message"),
            timestamp=source.get("timestamp", datetime.now()),
        )

    def to_dict(self) -> dict:
        """
        ConversationRecord インスタンスを Firestore に保存できるよう dict に変換します。
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def collection(db):
        """
        Firestore のコレクション参照を返します。
        """
        return db.collection(ConversationRecord.COLLECTION)

    def save(self, ref):
        """
        インスタンスの内容を Firestore に保存します。
        """
        doc_ref = ref.document(self.id)
        doc_ref.set(self.to_dict())

    @staticmethod
    def record_message(db, user_id: str, role: str, message: str):
        """
        会話の1メッセージ分を新規に作成し、Firestoreに保存します。
        """
        ref = ConversationRecord.collection(db)
        record = ConversationRecord(user_id=user_id, role=role, message=message)
        record.save(ref)
        return record

    @staticmethod
    def get_recent_messages(db, user_id: str, limit: int = 10, since: datetime = None):
        """
        指定ユーザーの会話履歴を新しい順で最大 limit 件取得し、古い順に並べ替えて返す。
        since が指定されていれば、その日時以降の履歴に絞り込む。
        """
        ref = ConversationRecord.collection(db).where(
            filter=FieldFilter("user_id", "==", user_id)
        )
        if since:
            ref = ref.where(filter=FieldFilter("timestamp", ">=", since))

        query = ref.order_by("timestamp", direction="DESCENDING").limit(limit)
        docs = query.stream()
        records = [ConversationRecord.from_dict(doc.to_dict()) for doc in docs]

        # 新しいものが先頭なので、時系列順に並べ替えて返す
        return list(reversed(records))

    @staticmethod
    def get_recent_conversation_str(db, user_id: str, limit: int = 10) -> str:
        """
        直近 limit 件のやり取りを、
        role: message
        role: message
        ...
        のフォーマットで連結した文字列として返します。
        """
        records = ConversationRecord.get_recent_messages(db, user_id, limit)
        lines = [f"{r.role}: {r.message}" for r in records]
        return "\n".join(lines)

    @staticmethod
    def delete_all_conversations(db, user_id: str):
        """
        該当ユーザーの会話履歴をすべて削除します。
        """
        ref = ConversationRecord.collection(db)
        query = ref.where(filter=FieldFilter("user_id", "==", user_id))
        docs = query.stream()
        for doc in docs:
            doc.reference.delete()

    @staticmethod
    def get_conversation_count(db, user_id: str) -> int:
        """
        該当ユーザーの会話が現在何回続いているかを返します（ドキュメント数をカウント）。
        """
        ref = ConversationRecord.collection(db)
        query = ref.where(filter=FieldFilter("user_id", "==", user_id))
        docs = query.stream()
        return len(list(docs))


# import os

# import firebase_admin
# from firebase_admin import firestore
# import google.generativeai as genai
# from datetime import datetime, timedelta

# genai.configure(api_key=os.environ["GENAI_API_KEY"])
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# # user_id="user123"、role="user"、message="こんにちは" を保存
# ConversationRecord.record_message(db, user_id="user123", role="user", message="こんにちは")
# ConversationRecord.record_message(db, user_id="user123", role="agent", message="こんにちは、どうしましたか？")

# # 直近10件を ConversationRecord のリストとして取得
# recent_records = ConversationRecord.get_recent_messages(db, "user123", limit=10)

# # フォーマットした文字列で取得
# conversation_text = ConversationRecord.get_recent_conversation_str(db, "user123", limit=10)
# print(conversation_text)

# # ConversationRecord.delete_all_conversations(db, "user123")

# count = ConversationRecord.get_conversation_count(db, "user123")
# print(count)  # 例: 10
