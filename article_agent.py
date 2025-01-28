import os
import json
import time
from typing import List
from conversation_record import ConversationRecord
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
from google.cloud.firestore_v1.vector import Vector
from article_content_fetcher import ArticleContentFetcher
from article_cleaner import ArticleCleaner
from article_summary_generator import ArticleSummaryGenerator
from web_searcher import WebSearcher
from article import Article
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from openai import OpenAI


# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# Firestore 初期化
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

# Google Custom Search
google_custom_search_api_key = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
google_search_cse_id = os.environ["GOOGLE_SEARCH_CSE_ID"]


GEMINI_MODEL = "gemini-2.0-flash-exp"
OPENAI_MODEL = "gpt-4o-mini"


class ArticleAgent:
    def __init__(
        self,
        db: firestore.Client,
        web_searcher: WebSearcher,
        user_id: str,
        model="gpt-4o-mini",
    ):
        self.client = OpenAI()
        self.db = db
        self.web_searcher = web_searcher
        self.content_fetcher = ArticleContentFetcher()
        self.article_cleaner = ArticleCleaner(GEMINI_MODEL)
        self.summary_generator = ArticleSummaryGenerator(GEMINI_MODEL)
        self.article_collection = Article.collection(self.db)
        self.user_id = user_id

        self.assistant = self.client.beta.assistants.create(
            instructions=(
                "あなたはエンジニアに最新の技術情報を伝えるアナウンサーです。\n"
                "以下の指示に従い、ユーザーから提供された質問への応答を作成してください。\n"
                "- 抽象的な表現は避け、具体的なツール名や企業名、専門用語を使用して詳細に伝えること\n"
                "- 日時や企業名、情報源などの詳細は省略せず、具体的に伝えること\n"
                "- URLやソースコード、括弧など自然に発話できない表現は避けること\n"
            ),
            model=model,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "search_articles",
                        "description": "Search articles relevant to the query from the article DB",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query string to find related articles",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "fetch_recent_messages",
                        "description": "Get the recent conversation history for the user",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                },
            ],
        )

    def answer_question(self, question: str) -> str:
        thread = self.client.beta.threads.create()
        self.client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=question
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=self.assistant.id
        )
        return self._poll_run_until_done(run)

    def _poll_run_until_done(self, run) -> str:
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=run.thread_id, run_id=run.id
            )
            if run.status == "requires_action":
                self._handle_tool_call(run)
            elif run.status == "completed":
                return self._get_final_message(run.thread_id)
            elif run.status in ("cancelled", "failed", "expired", "incomplete"):
                return f"[Run ended. status={run.status}]"
            time.sleep(1)

    def _handle_tool_call(self, run):
        tool_outputs = []
        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print("function_name: ", function_name)
            print("arguments: ", arguments)

            if function_name == "search_articles":
                result = self.search_articles(arguments["query"])
            elif function_name == "fetch_recent_messages":
                result = self.fetch_recent_messages()
            else:
                result = "[Unknown tool call]"

            tool_outputs.append({"tool_call_id": tool_call.id, "output": result})

        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=run.thread_id, run_id=run.id, tool_outputs=tool_outputs
        )

    def _get_final_message(self, thread_id: str) -> str:
        messages = self.client.beta.threads.messages.list(thread_id=thread_id)
        for msg in reversed(messages.data):
            if msg.role == "assistant":
                return msg.content[0].text.value
        return "[No assistant message found]"

    def create_by_query(self, query: str) -> List[Article]:
        search_results = self.web_searcher.search(query, num_results=3)
        articles = []

        for result in search_results:
            title = result["title"]
            url = result["url"]

            try:
                raw_content = self.content_fetcher.fetch(url)
                if not raw_content:
                    continue

                clean_result = self.article_cleaner.llm_clean_text(raw_content, title)
                clean_text = clean_result.get("clean_text", "")
                keyword = clean_result.get("keyword", "")
                summary = self.summary_generator.generate_summary(title, clean_text)

                article = Article(
                    title=title,
                    summary=summary,
                    url=url,
                    body=clean_text,
                    keyword=keyword,
                )
                article.save(self.article_collection)
                articles.append(article)

            except Exception as e:
                print(f"Failed to process article at {url}: {e}")

        return articles

    def search_articles(self, query: str) -> str:
        query_vector = genai.embed_content(
            model=Article.EMBEDDING_MODEL, content=query
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

        articles_section = self.format_articles(articles)
        return articles_section

    def format_articles(self, articles: list) -> str:
        articles_section = ""
        for index, article in enumerate(articles):
            title = article.get("title", "")
            url = self.clean_url(article.get("url", ""))
            summary = article.get("summary", "")
            body = article.get("body", "")

            if index == 0:
                articles_section += (
                    f"title: {title}\n"
                    f"url: {url}\n"
                    f"summary: {summary}\n"
                    f"body: {body[:3000]}\n\n"
                )
            else:
                articles_section += (
                    f"title: {title}\n" f"url: {url}\n" f"summary: {summary[:500]}\n\n"
                )
        return articles_section

    def clean_url(self, url: str) -> str:
        url = url.split("?")[0]
        return url

    def fetch_recent_messages(self) -> str:
        recent_records = ConversationRecord.get_recent_messages(
            self.db, self.user_id, limit=10
        )
        conversation_text = "\n".join(
            [f"{r.role}: {r.message}" for r in recent_records]
        )
        return conversation_text


# ==============================
# 実行例
# ==============================
# if __name__ == "__main__":
#     # ダミー初期化
#     db = firestore.client()
#     web_searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)

#     # インスタンス作成
#     user_id = "test_user"
#     article_assistant = ArticleAgent(db=db, web_searcher=web_searcher, user_id=user_id)

#     # 質問を投げる
#     question = "前回の質問の回答が曖昧だったので、もう一度詳細に回答してください"

#     response = article_assistant.answer_question(question)

#     # 結果を表示
#     print("Assistant Response:\n", response)
