import json
import google.generativeai as genai
from article import Article
from datetime import datetime, timedelta
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from static_news import StaticNews
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "sample_question": {"type": "STRING"},
    },
    "required": ["summary", "sample_question"],
}
EMBEDDING_MODEL = "models/text-embedding-004"


class StaticNewsGenerator:
    def __init__(self, db, model_name: str):
        self.db = db
        self.article_collection = Article.collection(db)
        self.static_news_collection = StaticNews.collection(db)
        self.model = genai.GenerativeModel(model_name)

    def _get_exclude_article_ids(self) -> list[str]:
        """
        過去7日間の StaticNews を取得して body をベクトル化。
        そのベクトルに最も近い Article を上位3件ずつ探して
        その Article.id のリストを返す。
        """
        cutoff_date = datetime.now() - timedelta(days=7)
        query = self.static_news_collection.where(
            filter=FieldFilter("published", ">=", cutoff_date)
        ).where(filter=FieldFilter("language_code", "==", "en"))
        docs = query.stream()

        exclude_ids = []

        for doc in docs:
            static_news_data = doc.to_dict()
            body = static_news_data.get("body", "")
            if not body:
                continue

            # StaticNews の body をベクトル化
            query_vector = genai.embed_content(model=EMBEDDING_MODEL, content=body)[
                "embedding"
            ]

            # Firestore Vector Search を用いて上位3件を取得
            if DistanceMeasure and Vector:
                vector_query = self.article_collection.select(
                    ["id", "title", "summary", "body", "url", "published"]
                ).find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(query_vector),
                    distance_measure=DistanceMeasure.EUCLIDEAN,
                    limit=3,
                )
                for a_doc in vector_query.stream():
                    article_data = a_doc.to_dict()
                    if article_data and "id" in article_data:
                        exclude_ids.append(article_data["id"])

        return list(set(exclude_ids))

    def create_prompt(self, language_code: str, exclude_ids: list[str] = None) -> str:
        # exclude_ids を考慮して記事一覧を取得
        result_strings = self.get_recent_articles(exclude_ids=exclude_ids)

        # prompt の組み立て
        article_list = "\n\n".join(result_strings)
        prompt_lines = [
            "あなたはエンジニアに最新の技術情報を伝えるアナウンサーです。",
            "以下に提供される記事一覧を分析し、もっとも重要なトピックをひとつ選んで伝えてください。"
            "",
            "質問: 本日のニュースを教えてください",
            "",
            "条件:",
            "- 抽象的な表現は避け、具体的なツール名や企業名、専門用語を使用して詳細に伝えること",
            "- 日時や企業名、情報源などの詳細は省略せず、具体的に伝えること",
            "- URLやソースコード、括弧など自然に発話できない表現は避けること",
            "- 複数の記事で取り上げられているテーマや大手企業の関連する記事を優先すること",
            "- その記事に関する20文字以下の短い質問例を作成すること",
            "",
            "出力形式:",
            "- summary: ニュースの原稿",
            "- sample_question: トピックに関する質問例",
            "",
            f"出力言語: '{language_code}'",
            "",
            "記事一覧:",
            f"{article_list}",
        ]
        return "\n".join(prompt_lines)

    def get_recent_articles(self, exclude_ids=None):
        """
        過去3日以内に公開された Article を取得し、
        exclude_ids が指定されていれば除外する。
        """
        cutoff_date = datetime.now() - timedelta(days=3)
        query = self.article_collection.where(
            filter=FieldFilter("published", ">=", cutoff_date)
        )

        if exclude_ids:
            # 指定された id を除外する条件
            query = query.where(filter=FieldFilter("id", "not-in", exclude_ids))

        docs = (
            query.order_by("published", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )

        result_strings = []
        for doc in docs:
            article_dict = doc.to_dict()
            # body の文字数が 200 以下の記事をスキップ
            body = article_dict.get("body", "")
            if len(body) <= 200:
                continue
            # 必要な情報をタイトル文字列に
            title = f"{article_dict.get('title', '')}"
            article_txt = f"{title}:\n{body[:200]}..."
            result_strings.append(article_txt)

        return result_strings

    def generate_news(self, language_code: str):
        """
        1. まず7日間の StaticNews を走査して、各 body をベクトル化し、
           関連する上位3件の Article.id を exclude_ids に追加
        2. 上記 exclude_ids を使って get_recent_articles から除外
        3. 生成した記事一覧でプロンプトを作成し、LLM から JSON 出力を受け取る
        4. パースして StaticNews として保存
        """
        # 1. 過去7日間の StaticNews から exclude_ids を作成
        exclude_ids = self._get_exclude_article_ids()

        # 2. exclude_ids を利用してプロンプトを作成
        prompt = self.create_prompt(language_code, exclude_ids=exclude_ids)

        # 3. LLM に投げて応答を受け取る
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
        try:
            parsed_result = json.loads(response.text)
            static_news = StaticNews(
                body=parsed_result["summary"],
                sample_question=parsed_result["sample_question"],
                language_code=language_code,
                published=datetime.now(),
            )
            static_news.save(self.static_news_collection)
            return static_news
        except (json.JSONDecodeError, KeyError):
            raise ValueError(
                "Failed to parse LLM response. Please check the prompt or the response format."
            )
