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

    def create_prompt(self, topic: str, language_code: str, region_code: str) -> str:
        """
        トピックに関連するニュースを3件分まとめて、
        JSON配列（要素: {title, body}）の形で要約を出力するようLLMへ指示するプロンプトを作成
        """
        lines = [
            "以下の指示に従い、ニュースの要約を3件作成してください。"
            "- topic, language_code, region_codeが提供されます",
            "- topicが多義語の場合は、region_codeが示す地域における最も一般的な解釈をしてください"
            "- topicに関する最新のニュースを3件検索して、language_codeの言語で要約を作成してください",
            "- 要約は後述の形式で出力してください\n",
            "提供する情報:",
            f"- topic: {topic}",
            f"- language_code: {language_code}",
            f"- region_code: {region_code}\n",
            "出力形式:"
            '```json\n[{"title":"","body":""},{"title":"","body":""},{"title":"","body":""}]\n```',
        ]
        return "\n".join(lines)

    def run(self, topic: str, language_code: str, region_code: str) -> list[dict]:
        """
        指定したトピックについてニュース要約を3件分生成し、
        戻り値としてtitleとbodyを持つ配列を返す
        """
        prompt = self.create_prompt(topic, language_code, region_code)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
        result: list[dict] = json.loads(response.text)
        return result
