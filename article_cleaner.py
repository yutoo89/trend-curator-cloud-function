import json
import google.generativeai as genai
from bs4 import BeautifulSoup
import re

CLEAN_TEXT_SCHEMA = {
    "type": "OBJECT",
    "properties": {"clean_text": {"type": "STRING"}},
    "required": ["clean_text"],
}


class ArticleCleaner:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, raw_text: str, title: str):
        prompt_lines = [
            "以下の指示に従い、スクレイピングで取得した記事を整形してください。",
            "- HTMLタグ、スクリプト、広告文、ページナビゲーション等の不要な要素は削除する"
            "- タイトルと無関係な内容は削除し、記事本文のみを残す",
            "- 改行や余分なスペースは削除する",
            "- 結果にタイトルは含めず、整形後の本文のみを返す",
            "\n",
            f"[title]\n{title}",
            f"[raw_text]\n{raw_text}",
        ]
        return "\n".join(prompt_lines)

    def clean_text(self, raw_text: str):
        if "<" in raw_text and ">" in raw_text:
            soup = BeautifulSoup(raw_text, "html.parser")
            raw_text = soup.get_text(separator=" ").strip()

        raw_text = re.sub(r"\s+", " ", raw_text).strip()

        return raw_text

    def llm_clean_text(self, raw_text: str, title: str):
        prompt = self.create_prompt(raw_text, title)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=CLEAN_TEXT_SCHEMA,
            ),
        )

        try:
            parsed_result = json.loads(response.text)
            clean_text = parsed_result["clean_text"]
            return clean_text
        except Exception as e:
            print(f"Failed to parse cleaned text response: {e}")
            return ""
