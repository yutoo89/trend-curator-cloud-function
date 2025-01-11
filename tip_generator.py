import json
import google.generativeai as genai

TIP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "manuscript": {"type": "STRING"},
    },
    "required": ["manuscript"],
}


class TipGenerator:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, topic: str, articles: list, language_code: str):
        articles_json = json.dumps(articles, ensure_ascii=False, indent=2)
        prompt_lines = [
            "話題になっているトピックと関連記事を提供します。",
            "第三者視点でこのトピックを紹介するニュース原稿を250文字以内で作成してください。",
            "- 抽象的・定性的な表現は省略し、ソフトウェアエンジニアの業務に役立つ具体的なTipsを作成します",
            "- タイトルの内容の簡潔な説明を冒頭に含め、記事を俯瞰する視点から解説します",
            "  - 例: 「~という記事が注目されています」「〜が話題となっています」",
            "- ソフトウェアエンジニアの業務に役立つTipsを含めます",
            "  - 例: 現在主流となっている類似のサービスとの比較、ベースとなった技術の解説",
            "- 抽象的・曖昧な表現は避け、固有名詞や具体例を多用します",
            "- 作成した原稿をそのままニュースとして読み上げても違和感のない表現にします",
            "- 原稿は'{language_code}'(language_code)で作成します",
            "",
            f"トピック: {topic}",
            "関連記事(JSON):",
            articles_json,
        ]
        return "\n".join(prompt_lines)

    def run(self, topic: str, articles: list, language_code: str):
        prompt = self.create_prompt(topic, articles, language_code)

        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TIP_SCHEMA,
            ),
        )
        try:
            manuscript = json.loads(response.text)["manuscript"]
            return manuscript
        except Exception as e:
            print(f"Failed to parse summary response: {e}")
            return {}
