import os
import json
import time
from datetime import datetime
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
from agent.tools import OPENAI_TOOLS, search_articles, fetch_recent_messages


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

OPENAI_ASSISTANTS_ID = "asst_HnywQuKkCXMIeSIOVqXVKqnz"
INSTRUCTIONS = (
    "あなたはエンジニアに最新の技術情報を伝えるアナウンサーです。\n"
    "以下の指示に従い、ユーザーから提供された質問への応答を作成してください。\n"
    "- 抽象的な表現は避け、具体的なツール名や企業名、専門用語を使用して詳細に伝えること\n"
    "- 日時や企業名、情報源などの詳細は省略せず、具体的に伝えること\n"
    "- URLやソースコード、括弧など自然に発話できない表現は避けること\n"
)


# https://platform.openai.com/docs/api-reference/threads/object
class ArticleAgent:
    def __init__(
        self,
        db: firestore.Client,
        web_searcher: WebSearcher,
        user_id: str,
        model=OPENAI_MODEL,
    ):
        self.client = OpenAI()
        self.db = db
        self.web_searcher = web_searcher
        self.content_fetcher = ArticleContentFetcher()
        self.article_cleaner = ArticleCleaner(GEMINI_MODEL)
        self.summary_generator = ArticleSummaryGenerator(GEMINI_MODEL)
        self.article_collection = Article.collection(self.db)
        self.user_id = user_id
        self.model = model

    @staticmethod
    def create_assistant(client: OpenAI, model: str):
        return client.beta.assistants.create(
            instructions=INSTRUCTIONS,
            model=model,
            tools=OPENAI_TOOLS,
        )

    def answer_question(self, question: str) -> str:
        # スレッドを作成
        thread = self.client.beta.threads.create(
            messages=[
                {"role": "user", "content": question},
            ]
        )
        # 実行とツール呼び出しをポーリング
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=OPENAI_ASSISTANTS_ID,
        )

        # ツール呼び出しが必要な場合は実行結果を返す
        if run.status == "requires_action":
            tool_outputs = []
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                tool_outputs.append(self.handle_tool_call(tool_call))

            run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )

        # 最終的な回答を取得
        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            # アシスタントからのテキストメッセージのみを抽出
            responses = [
                content.text.value
                for msg in messages.data
                if msg.role == "assistant"
                for content in msg.content
                if content.type == "text"
            ]
            answer = (
                "\n".join(responses) if responses else "No response from assistant."
            )
        else:
            answer = f"Error: {run.status}"

        # スレッドを削除してクリーンアップ
        self.client.beta.threads.delete(thread.id)
        return answer

    def handle_tool_call(self, tool_call):
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        if function_name == "search_articles":
            output = search_articles(
                article_collection=self.article_collection, query=arguments["query"]
            )
        elif function_name == "fetch_recent_messages":
            output = fetch_recent_messages(db=self.db, user_id=self.user_id)
        else:
            output = "[Unknown tool call]"

        return {
            "tool_call_id": tool_call.id,
            "output": json.dumps(output, ensure_ascii=False),
        }


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
#     question = "Appleの新製品Vision Proについて教えてください"

#     response = article_assistant.answer_question(question)

#     # 結果を表示
#     print("Assistant Response:\n", response)
