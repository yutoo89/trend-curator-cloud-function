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
from openai import OpenAI, AssistantEventHandler
from typing_extensions import override


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
        model="gpt-4o-mini",
        instructions="You are an AI that answers user queries about articles.",
    ):
        self.client = OpenAI()
        self.db = db
        self.web_searcher = web_searcher
        self.content_fetcher = ArticleContentFetcher()
        self.article_cleaner = ArticleCleaner(GEMINI_MODEL)
        self.summary_generator = ArticleSummaryGenerator(GEMINI_MODEL)
        self.article_collection = Article.collection(self.db)

        # Assistant(=モデル)を作成
        self.assistant = self.client.beta.assistants.create(
            instructions=instructions,
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
                            "properties": {
                                "user_id": {
                                    "type": "string",
                                    "description": "The user ID for which we want to retrieve past messages",
                                },
                            },
                            "required": ["user_id"],
                        },
                    },
                },
            ],
        )

    def answer_question(self, user_id: str, question: str) -> str:
        """
        ユーザーIDと質問を受け取り、Assistantを用いて回答を生成する。
        必要に応じて search_articles / fetch_recent_messages をツールとして呼び出して利用する。
        (ストリーミングは使わず、runのstatusをポーリングして最終回答を取得する)
        """

        # 1. 新しいスレッドを作成（会話単位の管理）
        thread = self.client.beta.threads.create()

        # 2. ユーザーからのメッセージをスレッドに追加
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=question,
        )

        # 3. ランを作成
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
        )

        # 4. イベントハンドラー (ツール呼び出し用) を用意
        event_handler = ArticleToolsEventHandler(self, self.client, thread.id)

        # 5. status が completed になるまでポーリング
        #    - 途中で requires_action になったらツール呼び出しを同期的に処理
        final_answer = self._poll_run_until_done(run, event_handler)

        return final_answer

    def _poll_run_until_done(self, run, event_handler) -> str:
        """run.status が completed になるまでポーリングし、最終アシスタントメッセージを返す"""
        while True:
            # 最新のRunステータスを取得（get→retrieve に変更）
            run = self.client.beta.threads.runs.retrieve(
                thread_id=run.thread_id,
                run_id=run.id,
            )
            status = run.status
            print(f"Current run status: {status}")

            if status == "requires_action":
                # ツール呼び出しを処理
                if run.required_action and run.required_action.submit_tool_outputs:
                    event_handler.handle_requires_action(run)
                time.sleep(1)

            elif status == "completed":
                # 最終回答を取得して返す
                return self._get_final_assistant_message(run.thread_id)

            elif status in ("queued", "in_progress"):
                # 実行中 → 少し待ってから再チェック
                time.sleep(1)

            elif status in ("cancelled", "failed", "expired", "incomplete"):
                # 失敗 or 中断
                return f"[Run ended. status={status}]"
            else:
                # 想定外のステータス
                return f"[Run ended. Unexpected status={status}]"

    def _get_final_assistant_message(self, thread_id: str) -> str:
        """スレッド内の最後のassistantメッセージを取得して返す"""
        messages = self.client.beta.threads.messages.list(thread_id=thread_id)

        # 後ろから探して最初に見つかったassistantロールのメッセージを返す
        for msg in reversed(messages.data):
            if msg.role == "assistant":
                # msg.content[0].text.value のように取り出す (バージョンにより差異あり)
                return msg.content[0].text.value
        return "[No assistant message found]"

    def create_by_query(self, query: str) -> List[Article]:
        # Perform the search and get the top 3 results
        search_results = self.web_searcher.search(query, num_results=3)
        articles = []

        for result in search_results:
            title = result["title"]
            url = result["url"]

            try:
                # Fetch the article content
                raw_content = self.content_fetcher.fetch(url)
                if not raw_content:
                    continue

                # Clean the content
                clean_result = self.article_cleaner.llm_clean_text(raw_content, title)
                clean_text = clean_result.get("clean_text", "")
                keyword = clean_result.get("keyword", "")
                summary = self.summary_generator.generate_summary(title, clean_text)

                # Create an Article instance
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
        """
        クエリに関連する記事をベクトル検索し、上位3件をフォーマットして返す。
        """
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
                    f"title: {title}\n"
                    f"url: {url}\n"
                    f"summary: {summary[:500]}\n\n"
                )
        return articles_section

    def clean_url(self, url: str) -> str:
        url = url.split("?")[0]
        return url

    def fetch_recent_messages(self, user_id: str) -> str:
        recent_records = ConversationRecord.get_recent_messages(
            self.db, user_id, limit=10
        )
        conversation_text = "\n".join([f"{r.role}: {r.message}" for r in recent_records])
        return conversation_text


class ArticleToolsEventHandler(AssistantEventHandler):
    """
    ツール呼び出しを処理するためのクラス。
    ただしストリーミングは使わず、`requires_action` のたびに同期呼び出しを行う。
    """

    def __init__(self, agent: ArticleAgent, client: OpenAI, thread_id: str):
        super().__init__()
        self.agent = agent
        self.client = client
        self.thread_id = thread_id
        self.responses = []

    def handle_requires_action(self, run):
        """
        run.required_action.submit_tool_outputs にツール呼び出し候補が入っているので処理し、
        同期メソッドsubmit_tool_outputsで結果を送信する
        """
        tool_outputs = []
        action = run.required_action.submit_tool_outputs

        for tool_call in action.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            print(f"function_name: {function_name}")
            print(f"args: {arguments}")

            if function_name == "search_articles":
                query_string = arguments["query"]
                result = self.agent.search_articles(query_string)
                tool_outputs.append({"tool_call_id": tool_call.id, "output": result})

            elif function_name == "fetch_recent_messages":
                target_user_id = arguments["user_id"]
                result = self.agent.fetch_recent_messages(target_user_id)
                tool_outputs.append({"tool_call_id": tool_call.id, "output": result})

        self._submit_tool_outputs(tool_outputs, run.id)

    def _submit_tool_outputs(self, tool_outputs, run_id):
        """
        同期的にツール実行の結果をサーバーに送信し、Runの状態を更新する。
        返り値は Runオブジェクト。
        """
        run_response = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
        )
        # ここでは「ツールを送信した」ログだけを記録する
        self.responses.append(f"[Tool outputs submitted; run status: {run_response.status}]")


# ==============================
# 実行例
# ==============================
# if __name__ == "__main__":
#     # ダミー初期化
#     db = firestore.client()
#     web_searcher = WebSearcher(google_custom_search_api_key, google_search_cse_id)

#     # インスタンス作成
#     article_assistant = ArticleAgent(db=db, web_searcher=web_searcher)

#     # 質問を投げる
#     user_id = "test_user"
#     question = "最近のAI技術ニュースを教えてください。"

#     response = article_assistant.answer_question(user_id, question)

#     # 結果を表示
#     print("Assistant Response:\n", response)
