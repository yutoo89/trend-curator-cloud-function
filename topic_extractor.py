import json
from datetime import datetime, timedelta
from typing import List, Dict

import google.generativeai as genai
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}


class TopicExtractor:
    def __init__(
        self, model_name: str, db: firestore.Client, article_collection, news_collection
    ):
        self.model = genai.GenerativeModel(model_name)
        self.db = db
        self.article_collection = article_collection
        self.news_collection = news_collection

    def _fetch_keywords_of_past_week(self, language_code: str) -> List[str]:
        """
        過去1週間に生成したニュースのキーワードを収集して返す。
        """
        one_week_ago = datetime.now() - timedelta(days=7)
        query = self.news_collection.where(
            filter=FieldFilter("published", ">=", one_week_ago)
        ).where(filter=FieldFilter("language_code", "==", language_code))
        docs = query.get()

        keywords = []
        for doc in docs:
            data = doc.to_dict()
            kw = data.get("keyword")
            if kw:
                keywords.append(kw.strip())
        return keywords

    def _get_recent_articles(self) -> List[Dict[str, str]]:
        """
        過去3日以内の記事を、Firestore の article_collection から取得する。
        返り値は、各記事が { "title": <タイトル>, "body": <本文> } の辞書となる。
        """
        cutoff_date = datetime.now() - timedelta(days=14)
        query = self.article_collection.where(
            filter=FieldFilter("published", ">=", cutoff_date)
        )
        docs = (
            query.order_by("published", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )

        articles = []
        for doc in docs:
            article_dict = doc.to_dict()
            title = article_dict.get("title", "")
            body = article_dict.get("body", "")
            articles.append({"title": title, "body": body})
        return articles

    def create_prompt(
        self,
        article_list: List[Dict[str, str]],
        exclude_topic_list: List[str],
        language_code: str,
    ) -> str:
        # 除外キーワードに一致する記事を除外し、所定の文字列形式に変換
        filtered_articles = []
        for article in article_list:
            title = article.get("title", "")
            body = article.get("body", "")
            should_exclude = False
            for excl in exclude_topic_list:
                if excl and excl in title:
                    should_exclude = True
                    break
            if not should_exclude:
                # filtered_articles.append(f"{title}:\n{body[:200]}...")
                filtered_articles.append(title)

        # 除外キーワード一覧を分かりやすく結合
        joined_excludes = (
            ", ".join(exclude_topic_list) if exclude_topic_list else "なし"
        )

        prompt_lines = [
            "以下の条件で、提供される記事タイトル一覧から、最も重要なトピックをひとつだけ抽出してください。",
            "- 除外キーワードに重複・類似するトピックは絶対に選ばないこと",
            "- トピックは抽象的な概念ではなく、具体的なツール名やサービス名などの固有名詞とすること",
            "  - 悪い例: `AI`",
            "  - 良い例: `DeepSeek R1`",
            "",
            f"除外キーワード: '{joined_excludes}'",
            "",
            "記事一覧:",
            "\n".join(filtered_articles),
        ]
        return "\n".join(prompt_lines)

    def extract_topic(
        self,
        language_code: str = "ja",
    ) -> dict:
        exclude_topic_list = self._fetch_keywords_of_past_week(language_code)
        article_list = self._get_recent_articles()

        prompt = self.create_prompt(article_list, exclude_topic_list, language_code)

        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TOPIC_SCHEMA,
            ),
        )
        try:
            result = json.loads(response.text)
        except Exception as e:
            print(f"LLMからの応答のパースに失敗しました: {e}")
            raise ValueError(f"LLMからの応答のパースに失敗しました: {e}")

        if "topic" not in result:
            print("LLMの応答に 'topic' キーが含まれていません。")
            raise KeyError("LLMの応答に 'topic' キーが含まれていません。")
        return result["topic"]
