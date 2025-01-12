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

    def create_prompt(self, query: str, exclude_queries: list[str] = None):
        prompt_lines = [
            f"以下のカテゴリから連想される最新の流行キーワードをランダムに3つ生成してください。",
            f"カテゴリ: {query}",
            "以下の条件を満たすようにしてください:",
            "- カテゴリ内で注目されている最新のテーマのうち、特にエンジニアに関連する専門用語を選択する",
            "- キーワードが多義語の場合は必要最低限のコンテキストをスペース区切りで含める",
            "- カテゴリそのものやその類語、抽象的すぎるキーワードや一般名詞は禁止とする",
            "良い例: 「生成AI」 => 'RAG AI', '画像生成 ライブラリ', 'AI agent'",
            "悪い例: 「生成AI」 => '生成AIモデル', '生成AI 課題', '生成AIビジネス応用'",
        ]
        
        if exclude_queries:
            prompt_lines.extend([
                f"- 以下のキーワードやその類語を含まないこと:\n{", ".join(exclude_queries)}",
            ])

        return "\n".join(prompt_lines)

    def generate_keywords(self, query: str, exclude_queries: list[str] = None):
        prompt = self.create_prompt(query, exclude_queries)

        prompt = self.create_prompt(query)
        print(f"[INFO] Generated prompts:\n{prompt}")

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
            print(f"Failed to parse related keywords response: {e}")
            return []
