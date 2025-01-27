import json
import google.generativeai as genai


class ArticleSummaryGenerator:
    SUMMARY_SCHEMA = {
        "type": "OBJECT",
        "properties": {"summary": {"type": "STRING"}},
        "required": ["summary"],
    }

    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, title: str, content: str):
        prompt_lines = [
            "以下の指示に従い、記事のタイトルと本文を要約してください。",
            "- 専門用語やツール名、企業名などの具体的な情報をできるだけ含めること",
            "- 要約は300文字程度に簡潔にまとめること",
            "\n",
            f"[title]\n{title}",
            f"[content]\n{content}",
        ]
        return "\n".join(prompt_lines)

    def generate_summary(self, title: str, content: str):
        prompt = self.create_prompt(title, content)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=self.SUMMARY_SCHEMA,
            ),
        )
        parsed_result = json.loads(response.text)
        return parsed_result.get("summary", "")
