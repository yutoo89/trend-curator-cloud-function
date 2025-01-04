import json
import google.generativeai as genai
import typing_extensions as typing


RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING"},
            "body": {"type": "STRING"},
        },
        "required": ["title", "body"],
    },
}


class GeminiTrendCurator:

    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, topic: str) -> str:
        """
        トピックに関連するニュースを3件分まとめて、
        JSON配列（要素: {title, body}）の形で要約を出力するようLLMへ指示するプロンプトを作成
        """
        lines = [
            f"あなたは有能なニュースアナリストです。",
            f"以下のトピックに関する、最近のニュースを探して3件の要約を生成してください。",
            "それぞれのニュースに対し、titleとbodyをJSON形式（配列）で出力してください。",
            "必ず以下の形式で出力してください:",
            '```json\n[{"title":"","body":""},{"title":"","body":""},{"title":"","body":""}]\n```',
            f"トピック: {topic}",
        ]
        return "\n".join(lines)

    def run(self, topic: str) -> list[dict]:
        """
        指定したトピックについてニュース要約を3件分生成し、
        戻り値としてtitleとbodyを持つ配列を返す
        """
        prompt = self.create_prompt(topic)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
        result: list[dict] = json.loads(response.text)
        return result
