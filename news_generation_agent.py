from datetime import datetime, timedelta
import json
from typing import List
from openai import OpenAI
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore

from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner
from article_summary_generator import ArticleSummaryGenerator
from web_searcher import WebSearcher
from article import Article
from news import News
from topic_extractor import TopicExtractor
from agent.tools import (
    NEWS_GENERATION_TOOLS,
    vector_db_article_search,
    get_article_title_url_list,
    get_article_from_title_url,
)
from user import LANGUAGE_CODE

GEMINI_MODEL = "gemini-1.5-flash"
TOPIC_GEMINI_MODEL = "gemini-1.5-pro"
OPENAI_MODEL = "gpt-4o-mini"

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "news_response",
        "schema": {
            "type": "object",
            "properties": {
                "news_content": {"type": "string"},
                "sample_question": {"type": "string"},
            },
            "required": ["news_content", "sample_question"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

OPENAI_ASSISTANTS_ID = "asst_jqm2BoWMBB5fnyXRc3UsA72L"

INSTRUCTIONS = (
    "あなたはエンジニアに最新の技術情報を伝えるアナウンサーです。\n"
    "ユーザーから提供された情報に基づき、以下の条件を満たすニュースを生成してください。\n"
    "- 抽象的な表現は避け、具体的なツール名や企業名、専門用語を使用して詳細に伝えること\n"
    "- 日時や企業名、情報源などの詳細は省略せず、具体的に伝えること\n"
    "- URLやソースコード、括弧書きなど自然に発話できない表現は避けること"
)


class NewsGenerationAgent:
    def __init__(
        self,
        db: firestore.Client,
        web_searcher: WebSearcher,
        model=OPENAI_MODEL,
    ):
        self.client = OpenAI()
        self.db = db
        self.web_searcher = web_searcher
        self.content_fetcher = ArticleContentFetcher()
        self.article_cleaner = ArticleCleaner(GEMINI_MODEL)
        self.summary_generator = ArticleSummaryGenerator(GEMINI_MODEL)
        self.article_collection = Article.collection(self.db)
        self.news_collection = News.get_collection(self.db)
        self.extractor = TopicExtractor(
            model_name=TOPIC_GEMINI_MODEL,
            db=db,
            article_collection=self.article_collection,
            news_collection=self.news_collection,
        )
        self.model = model

    @staticmethod
    def create_assistant(client: OpenAI, model: str):
        return client.beta.assistants.create(
            instructions=INSTRUCTIONS,
            model=model,
            tools=NEWS_GENERATION_TOOLS,
        )

    def _fetch_keywords_of_past_week(self, language_code: str) -> List[str]:
        """
        過去1週間に生成したニュースのキーワードを収集して返す。
        """
        one_week_ago = datetime.now() - timedelta(days=7)
        ref = News.get_collection(self.db)
        query = ref.where(filter=FieldFilter("published", ">=", one_week_ago)).where(
            filter=FieldFilter("language_code", "==", language_code)
        )
        docs = query.get()

        keywords = []
        for doc in docs:
            data = doc.to_dict()
            kw = data.get("keyword")
            if kw:
                keywords.append(kw.strip())
        return keywords

    def _get_recent_articles(self):
        cutoff_date = datetime.now() - timedelta(days=3)
        query = self.article_collection.where(
            filter=FieldFilter("published", ">=", cutoff_date)
        )

        docs = (
            query.order_by("published", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )

        result_strings = []
        for doc in docs:
            article_dict = doc.to_dict()
            title = article_dict.get("title", "")
            body = article_dict.get("body", "")
            if len(body) > 200:
                result_strings.append(f"{title}:\n{body[:200]}...")

        return result_strings

    def prompt(self, language_code: str, topic: str) -> str:
        related_article_str = vector_db_article_search(
            self.article_collection, query=topic
        )

        language_instructions = (
            "- 質問の回答は、300文字以内で作成すること\n- アルファベット表記の固有名詞は日本における一般的な読みに変換すること\n  - 例: `ChatGPT` => `チャットジーピーティー`"
            if language_code == LANGUAGE_CODE["JA"]
            else "- 質問の回答は、500文字以内で作成すること"
        )

        prompt_lines = [
            "あなたはエンジニアに最新の技術情報を伝えるアナウンサーです。",
            "下記のトピックに関する技術情報をデータベースとウェブを用いて調査してください。",
            "その調査結果を使用して質問に回答してください。",
            "",
            f"トピック: {topic}",
            "質問: ニュースを教えてください",
            f"",
            "条件:",
            "- 具体的な技術情報やツール名、企業名、日付、情報ソースなどの詳細情報を用いて具体的に回答すること",
            "- トピックに関する20文字程度の短い質問例を作成すること",
            "- URLやソースコード、括弧書きなどの自然に発話できない表現は避けること",
            language_instructions,
            "",
            "出力フォーマット:",
            "- news_content: ニュースの原稿",
            "- sample_question: トピックに関する質問例",
            "",
            f"出力言語: '{language_code}'",
            "",
            "関連する記事:",
            related_article_str,
        ]
        return "\n".join(prompt_lines)

    def extract_topic(self) -> str:
        return self.extractor.extract_topic()

    def create(self, language_code: str, topic: str) -> News:
        prompt = self.prompt(language_code=language_code, topic=topic)

        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
        )

        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=OPENAI_ASSISTANTS_ID,
            response_format=RESPONSE_FORMAT,
            tools=NEWS_GENERATION_TOOLS,
        )

        # ツール呼び出しが必要な場合、その処理を実施
        while run.status == "requires_action":
            tool_outputs = []
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                if function_name == "vector_db_article_search":
                    output = vector_db_article_search(
                        article_collection=self.article_collection,
                        query=arguments["query"],
                    )
                elif function_name == "get_article_title_url_list":
                    output = get_article_title_url_list(
                        web_searcher=self.web_searcher,
                        query=arguments["query"],
                    )
                elif function_name == "get_article_from_title_url":
                    output = get_article_from_title_url(
                        content_fetcher=self.content_fetcher,
                        article_cleaner=self.article_cleaner,
                        summary_generator=self.summary_generator,
                        article_collection=self.article_collection,
                        title=arguments["title"],
                        url=arguments["url"],
                    )
                else:
                    output = "[Unknown tool call]"
                tool_outputs.append(
                    {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(output, ensure_ascii=False),
                    }
                )

            # ツールの出力を送信して再度ポーリング
            run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )

        # 最終メッセージから生成結果を取得
        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            assistant_messages = [m for m in messages.data if m.role == "assistant"]

            if assistant_messages:
                final_msg = assistant_messages[-1]
                json_text = next(
                    (c.text.value for c in final_msg.content if c.type == "text"), None
                )
                if json_text:
                    parsed_result = json.loads(json_text)
                    news_content = parsed_result["news_content"]
                    sample_question = parsed_result["sample_question"]
                    keyword = topic
                else:
                    raise ValueError("Response does not contain valid JSON text.")

        self.client.beta.threads.delete(thread.id)

        if not news_content or not sample_question or not keyword:
            print(
                "[ERROR] Failed to news generation - One or more fields are empty or None."
            )
            return

        news_obj = News(
            content=news_content,
            sample_question=sample_question,
            keyword=keyword,
            language_code=language_code,
        )
        news_collection = News.get_collection(self.db)
        news_obj.save(news_collection)

        return news_obj
