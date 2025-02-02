import json
from openai import OpenAI
from firebase_admin import firestore
from datetime import datetime

from user import User, ANSWER_STATUS
from news import News
from article import Article
from agent.tools import (
    ANSWER_TOOLS,
    vector_db_article_search,
)

GEMINI_MODEL = "gemini-1.5-flash"
OPENAI_MODEL = "gpt-4o-mini"

INAPPROPRIATE_KEYWORDS = [
    "殺す",
    "自殺",
    "クレジットカード情報",
    "脅迫",
    "違法行為",
]

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_response",
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

OPENAI_ASSISTANTS_ID = "asst_ot0MWbWKMAeRsWOmLX6QZ8cG"

INSTRUCTIONS = (
    "あなたはエンジニアに最新の技術情報を提供するアナウンサーです。\n"
    "ユーザーから提供された情報に基づき、以下の条件を満たす回答を生成してください。\n"
    "- 抽象的な表現は避け、具体的なツール名や企業名、専門用語を使用して詳細に伝えること\n"
    "- 日時や企業名、情報源などの詳細は省略せず、具体的に伝えること\n"
    "- URLやソースコード、括弧書きなど自然に発話できない表現は避けること"
)


class AnswerAgent:
    def __init__(
        self,
        db: firestore.Client,
        model: str = OPENAI_MODEL,
    ):
        self.client = OpenAI()
        self.db = db
        self.model = model
        self.article_collection = Article.collection(self.db)

    @staticmethod
    def create_assistant(client: OpenAI, model: str):
        return client.beta.assistants.create(
            instructions=INSTRUCTIONS,
            model=model,
            tools=ANSWER_TOOLS,
        )

    def _is_inappropriate(self, question: str) -> bool:
        """非常に簡易的な不適切ワード判定。実運用ではOpenAI Moderation等を利用推奨。"""
        for kw in INAPPROPRIATE_KEYWORDS:
            if kw in question:
                return True
        return False

    def prompt(self, question: str, language_code: str) -> str:
        news_list = News.get_recent_news(db=self.db, language_code=language_code)
        today = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        prompt_lines = [
            "以下の質問に簡潔に回答してください。",
            "",
            f"質問: {question}",
            "",
            "条件:",
            "- 必要に応じて会話履歴や記事を参照し、事実に基づく回答をすること",
            "- URLやソースコード、括弧書きなど自然に発話できない表現は避けること",
            "- 犯罪や猥褻に関連する不適切な質問には回答せず、その旨を伝えること",
            "",
            f"出力言語: '{language_code}",
            f"現在の日付: '{today}'",
            "",
            "最近のニュース:",
            news_list,
        ]
        return "\n".join(prompt_lines)

    def answer(self, user_id: str, question: str) -> str:
        user_ref = User.collection(self.db)
        user = User.get(user_ref, user_id)

        prompt = self.prompt(question=question, language_code=user.language_code)
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
            tools=ANSWER_TOOLS,
        )

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
                elif function_name == "get_recent_conversation_history":
                    conversation_text = user.format_conversations(self.db)
                    output = conversation_text
                else:
                    raise ValueError("Response does not contain valid JSON text.")

                tool_outputs.append(
                    {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(output, ensure_ascii=False),
                    }
                )

            run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )

        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            assistant_messages = [m for m in messages.data if m.role == "assistant"]
            if assistant_messages:
                final_msg = assistant_messages[-1]
                # JSON Schema に従って "answer" フィールドを取り出す
                json_text = next(
                    (c.text.value for c in final_msg.content if c.type == "text"), None
                )
                if json_text:
                    parsed_result = json.loads(json_text)
                    agent_answer = parsed_result["answer"]
                else:
                    raise RuntimeError("適切な回答を生成できませんでした。")
            else:
                raise RuntimeError("回答が得られませんでした。")
        else:
            raise RuntimeError("回答を生成できませんでした。別の質問をお試しください。")

        # スレッドのリソースを削除
        self.client.beta.threads.delete(thread.id)

        return agent_answer
