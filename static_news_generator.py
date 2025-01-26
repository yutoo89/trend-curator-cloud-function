import json
import google.generativeai as genai
from article import Article
from datetime import datetime, timedelta
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from static_news import StaticNews

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "sample_question": {"type": "STRING"},
    },
    "required": ["summary", "sample_question"],
}


class StaticNewsGenerator:
    def __init__(self, db, model_name: str):
        self.article_collection = Article.collection(db)
        self.static_news_collection = StaticNews.collection(db)
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, language_code: str):
        result_strings = self.get_recent_articles()
        article_list = "\n- ".join(result_strings)
        prompt_lines = [
            "以下にWEBエンジニア向けのニュース記事のタイトルのリストを提供します。",
            "この中から重要と思われる記事をひとつ選び、ひとことの紹介文を作成してください。",
            "",
            "条件:",
            "- トピックの紹介文は、話し言葉で簡潔かつ丁寧に作成すること",
            "- 複数の記事で取り上げられているテーマや大手企業の関連する記事を優先すること",
            "- その記事に関する20文字以下の短い質問例を作成すること",
            "  - 例: OpenAIがGUIエージェント「Operator」を発表 => 「Operator」に類似の技術にはどんなものがありますか？",
            "",
            "出力形式:",
            "- summary: トピックのひとことの説明",
            "- sample_question: トピックに関する質問例",
            "",
            f"出力言語: '{language_code}'",
            "",
            "記事一覧:",
            f"- {article_list}",
        ]
        return "\n".join(prompt_lines)

    def get_recent_articles(self, exclude_ids=None):
        cutoff_date = datetime.now() - timedelta(days=3)
        query = self.article_collection.where(
            filter=FieldFilter("published", ">=", cutoff_date)
        )

        if exclude_ids:
            query = query.where(filter=FieldFilter("id", "not-in", exclude_ids))

        docs = (
            query.order_by("published", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )

        result_strings = []

        for doc in docs:
            article_dict = doc.to_dict()
            article_data = [
                f"{article_dict.get('title', '')}",
            ]

            article_txt = "\n".join(article_data)
            result_strings.append(article_txt)
        return result_strings

    def generate_news(self, language_code: str):
        """
        記事データをもとに重大な話題を生成する。
        """
        prompt = self.create_prompt(language_code)
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


# import os

# import firebase_admin
# from firebase_admin import firestore
# import google.generativeai as genai
# from datetime import datetime, timedelta

# genai.configure(api_key=os.environ["GENAI_API_KEY"])
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# language_code = "ja"
# generator = StaticNewsGenerator(db, "gemini-1.5-flash")
# result = generator.generate_news(language_code)
# print(result)
