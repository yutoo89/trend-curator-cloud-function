import re
from datetime import date
from typing import Union
from article import Article
from conversation_record import ConversationRecord
import google.generativeai as genai
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_query import FieldFilter
from ng_words_list import NG_WORDS
from static_news import StaticNews
from datetime import date, datetime, time


class RAGAnswerGenerator:
    def __init__(self, db):
        self.db = db
        self.article_collection = Article.collection(db)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def check_daily_limit(
        self, user_id: str, language_code: str, limit_per_day: int = 5
    ):
        """
        当日のユーザ発言( role="user" )回数を調べ、上限に達していれば言語に応じた警告文を返す。
        達していなければ None を返す。
        """
        # 今日の 00:00:00 を since として指定
        today_start = datetime.combine(date.today(), time.min)
        # 直近50件、かつ本日以降のデータだけを取得
        all_recent_records = ConversationRecord.get_recent_messages(
            self.db, user_id, limit=50, since=today_start
        )
        # 本日 user ロールのメッセージ数をカウント
        todays_user_count = sum(1 for r in all_recent_records if r.role == "user")
        if todays_user_count >= limit_per_day:
            if language_code != "ja":
                return (
                    "Today's usage limit has been reached. Please try again tomorrow."
                )
            else:
                return "本日の利用回数が上限に達しました。また明日ご利用ください。"
        return None

    def is_inappropriate(self, user_message: str) -> bool:
        """
        ユーザの発言内容が不適切（卑猥・犯罪等）かどうかを判定します。
        NGワードは外部ファイル ng_words_list.py の NG_WORDS から読み込み。
        """
        lowered = user_message.lower()
        for ng in NG_WORDS:
            if ng.lower() in lowered:
                return True
        return False

    def generate_answer(
        self, user_id: str, user_message: Union[str, None], language_code: str
    ) -> str:
        if not user_message:
            return self._generate_agent_message_only(user_id, language_code)

        # --- Step 1. 日次利用回数チェック ---
        limit_message = self.check_daily_limit(user_id, language_code, limit_per_day=5)
        if limit_message:
            return limit_message

        # --- Step 2. 不適切表現チェック ---
        if self.is_inappropriate(user_message):
            if language_code == "ja":
                return "不適切な表現のためお答えできません。"
            else:
                return "We cannot respond due to inappropriate request."

        # --- Step 3. ユーザ発言をConversationRecordに追加 ---
        ConversationRecord.record_message(self.db, user_id, "user", user_message)

        # --- Step 4. ベクトル検索で関連する記事 (上位3件) を取得 ---
        recent_records = ConversationRecord.get_recent_messages(
            self.db, user_id, limit=10
        )
        conversation_text = "\n".join(
            [f"{r.role}: {r.message}" for r in recent_records]
        )

        # Embeddingを生成（実際の環境に合わせて実装）
        query_vector = genai.embed_content(
            model=Article.EMBEDDING_MODEL,
            content=user_message,
        )["embedding"]

        vector_query = self.article_collection.select(
            ["id", "title", "summary", "body", "url", "published"]
        ).find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.EUCLIDEAN,
            limit=3,
        )

        articles = []
        for doc in vector_query.stream():
            article_data = doc.to_dict()
            if article_data and "id" in article_data:
                articles.append(article_data)

        # --- Step 5. 日本語プロンプトを組み立てて LLM に問い合わせ ---
        prompt = self.build_prompt(
            user_message=user_message,
            conversation_text=conversation_text,
            articles=articles,
            language_code=language_code,
        )

        response = self.model.generate_content(prompt)
        answer = response.text.strip()

        ConversationRecord.record_message(self.db, user_id, "agent", answer)

        return answer

    def clean_url(self, url: str):
        # url = re.sub(r"https?://", "", url)
        url = url.split("?")[0]
        return url

    def build_prompt(
        self,
        user_message: str,
        conversation_text: str,
        articles: list,
        language_code: str,
    ) -> str:
        # 会話履歴
        conversation_lines = []
        for line in conversation_text.split("\n"):
            conversation_lines.append(line)
        conversation_history_text = "\n".join(conversation_lines)

        # 参考記事
        articles_section = ""
        for index, article in enumerate(articles):
            title = article.get("title", "")
            url = self.clean_url(article.get("url", ""))
            summary = article.get("summary", "")
            body = article.get("body", "")

            if index == 0:
                # 最初の1件は body も与える
                articles_section += (
                    f"title: {title}\n"
                    f"url: {url}\n"
                    f"summary: {summary}\n"
                    f"body: {body[:3000]}\n\n"
                )
            else:
                # 2件目以降は summary のみカットして追加
                articles_section += (
                    f"title: {title}\n" f"url: {url}\n" f"summary: {summary[:500]}\n\n"
                )

        prompt_lines = [
            "あなたはエンジニアと会話するAIです。",
            "これまでの会話履歴、および参考記事を踏まえて、以下の質問に簡潔な回答を生成してください。",
            "",
            "【質問】",
            user_message,
            "",
            "【会話履歴】",
            conversation_history_text,
            "",
            "【回答条件】",
            "- 過去に提供した情報と重複や類似を避けること。",
            "- 抽象的な内容はなるべく避け、具体的な情報を含めること。",
            "- URLやコード、括弧など自然に発話できない表現は避けること。",
            f"- 回答は言語コード'{language_code}'で生成すること。",
            "- 50文字程度で回答すること。",
            "",
            "【参考記事】",
            articles_section,
        ]

        prompt = "\n".join(prompt_lines)
        return prompt

    def _generate_agent_message_only(self, user_id: str, language_code: str) -> str:
        """
        user_message が None の場合にのみ呼ばれる。
        ルールに従って「今日のニュース」「質問例」を返し、必要に応じて会話履歴に 'agent' で追加。
        3回目以降は会話履歴に追加せず返す。
        """
        # 今日の 00:00:00 を since として指定して当日分のみ取得
        today_start = datetime.combine(date.today(), time.min)
        all_recent_records = ConversationRecord.get_recent_messages(
            self.db, user_id, limit=50, since=today_start
        )
        # 今日の agent ロールの発言数をカウント
        todays_agent_count = sum(1 for r in all_recent_records if r.role == "agent")

        # 最新のニュースを1件取得
        static_news_collection = StaticNews.collection(self.db)
        query = (
            static_news_collection.where(
                filter=FieldFilter("language_code", "==", language_code)
            )
            .order_by("published", direction="DESCENDING")
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            # ニュースが見つからない場合のfallback
            # 言語コードごとに文言を分岐
            if language_code == "ja":
                return "本日のニュースはまだありません。"
            else:
                return "No news is available today."

        doc_id = docs[0].id
        latest_static_news = StaticNews.get(static_news_collection, doc_id)

        # 言語コードごとに「今日のニュース」と「質問例」の文言を切り替え
        if language_code == "ja":
            # 日本語
            todays_news_message = "".join(
                [
                    "テックキュレーターの本日のニュースです。",
                    latest_static_news.body,
                ]
            )
            sample_question_message = "".join(
                [
                    "本日のニュースです。",
                    latest_static_news.body,
                    "何か質問がある場合は、「質問」と宣言した後に質問してみてください。たとえば、「質問、",
                    latest_static_news.sample_question,
                    "」のように言ってみてください。",
                ]
            )
        else:
            # 英語 (例)
            todays_news_message = "".join(
                [
                    "Here is today's news curated by Tech: ",
                    latest_static_news.body,
                ]
            )
            sample_question_message = "".join(
                [
                    "Today's news: ",
                    latest_static_news.body,
                    "If you have any questions, please say 'Question' first, then ask. For example, 'Question, ",
                    latest_static_news.sample_question,
                    "'.",
                ]
            )

        # 回数による分岐
        if todays_agent_count == 0:
            # 0回目 → 今日のニュースを会話履歴に追加
            ConversationRecord.record_message(
                self.db, user_id, "agent", todays_news_message
            )
            return todays_news_message
        elif todays_agent_count == 1:
            # 1回目 → 質問例を会話履歴に追加
            ConversationRecord.record_message(
                self.db, user_id, "agent", sample_question_message
            )
            return sample_question_message
        else:
            # 2回目以上 → 今日のニュース (会話履歴には追加しない)
            return todays_news_message
