import json
import google.generativeai as genai

RELATED_KEYWORDS_SCHEMA = {
    "type": "OBJECT",
    "properties": {"keywords": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["keywords"],
}


class RelatedKeywordGenerator:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, query: str):
        prompt_lines = [
            f"以下のカテゴリから連想されるキーワードをランダムに3つ生成してください。",
            f"カテゴリ: {query}",
            "以下の条件を満たすようにしてください:",
            "- カテゴリ内で注目されているテーマのうち、特にエンジニア業務で頻出するキーワードを選択する",
            "- キーワードが多義語の場合は必要最低限のコンテキストをスペース区切りで含める",
            "- カテゴリそのものやその類語、抽象的すぎるキーワードは禁止とする",
            "良い例: 「生成AI」 => 「プロンプト」「画像生成 AI」「AI agent」",
            "悪い例: 「生成AI」 => 「生成AIモデル」「生成AIの課題」「生成AIビジネス応用」",
            "",
            "出力は JSON 形式で、以下のフィールドを必ず含めてください:",
            "- keywords: キーワードの配列（3つ）",
        ]
        return "\n".join(prompt_lines)

    def generate_keywords(self, query: str):
        prompt = self.create_prompt(query)

        prompt = self.create_prompt(query)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RELATED_KEYWORDS_SCHEMA,
            ),
        )

        try:
            parsed_result = json.loads(response.text)
            keywords = parsed_result["keywords"][:3]
            return keywords
        except Exception as e:
            print(f"Failed to parse co-occurring keywords response: {e}")
            return []
