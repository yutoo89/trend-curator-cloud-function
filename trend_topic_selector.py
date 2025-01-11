import json
import google.generativeai as genai

TREND_TOPIC_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "selected_topic": {"type": "STRING"},
        "related_urls": {"type": "ARRAY", "items": {"type": "STRING"}},
        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["selected_topic", "related_urls", "keywords"],
}


class TrendTopicSelector:
    """
    取得した検索結果(最大40件)の上位トピック傾向を見て、
    固有名詞(ライブラリ名、ツール名、企業名など)が含まれる具体的リリース情報等を
    1つだけ抽出し、関連URL、keywords を返す。
    """

    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(
        self,
        query: str,
        search_results: list,
        exclude_keywords: list,
        language_code: str,
    ):
        """
        「まとめ」「ブログ」などの複数記事を羅列するページは除外。
        exclude_keywords と重複・類似するトピックも除外するように促す。
        固有名詞を含む具体的なトピックを優先抽出。
        """
        search_results_json = json.dumps(search_results, ensure_ascii=False, indent=2)

        prompt_lines = [
            f"Google検索で '{query}'をキーワードとして取得した記事一覧を提供します。",
            "これらの結果からソフトウェアエンジニアの業務に役立つ具体的なトピックを1つ抽出してください。",
            "- ツール名などの固有名詞を含むトピックや複数の記事に共通するテーマを優先的に抽出します",
            "- 経済的なニュースや複数記事のまとめのような記事は除外します",
            "- インストールやチュートリアル関連の記事など、コードやコマンドが主体の記事は除外します",
            "- exclude_keywords と重複・類似する記事は除外します",
            "",
            "出力は JSON 形式で以下のフィールドを必ず含めてください:",
            "- selected_topic: トピック内容（固有名詞含む）",
            "- related_urls: そのトピックに関連するURL一覧 (最大5件)",
            "- keywords: そのトピックに関連するキーワード群 (固有名詞)",
            "",
            f"出力言語は '{language_code}' です。",
            "",
            f"exclude_keywords: {exclude_keywords}",
            "",
            "記事一覧(JSON):",
            search_results_json,
        ]
        return "\n".join(prompt_lines)

    def select_trend_topic(
        self,
        query: str,
        search_results: list,
        exclude_keywords: list,
        language_code: str,
    ):
        prompt = self.create_prompt(
            query, search_results, exclude_keywords, language_code
        )

        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TREND_TOPIC_SCHEMA,
            ),
        )
        try:
            parsed_result = json.loads(response.text)
            selected_topic = parsed_result["selected_topic"]
            related_urls = parsed_result["related_urls"]
            keywords = parsed_result["keywords"]
            return selected_topic, related_urls, keywords
        except Exception as e:
            print(f"Failed to parse trend topic response: {e}")
            return "", [], []
