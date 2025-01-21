import json
import google.generativeai as genai
from article_content_fetcher import ArticleContentFetcher
from web_searcher import WebSearcher

NEWS_TOPIC_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "introduction": {"type": "STRING"},
        "query": {"type": "STRING"},
        "related_urls": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["introduction", "query", "related_urls"],
}


class NewsTopicSelector:
    def __init__(self, model_name: str, searcher: WebSearcher):
        self.model = genai.GenerativeModel(model_name)
        self.searcher = searcher

    def create_prompt(
        self,
        search_results: list,
        language_code: str,
        exclude: list[str] = None,
    ):
        search_results_json = json.dumps(search_results, ensure_ascii=False, indent=2)

        prompt_lines = [
            "以下にWEBエンジニア向けのニュース記事のタイトルとURLのリストを提供します。",
            "今注目されている具体的なツールや機能、使い方をひとつ選択し、詳細を調べるためのキーワード(ツール名)を生成してください。",
            "また、そのツールや機能、使い方の短い説明文を作成してください。",
            "",
            "条件:",
            "- WEBエンジニア向けの最新のツール、API、新機能、使い方の具体的な情報を選択すること",
            "  - 知識に頼らず、必ず提供された記事の中から最新のトピックを選択すること",
            "  - 直近数週間以内のニュースを優先し、半年以上前から知られている話題は除外すること",
            "- 検索キーワードは、ツールや機能の固有名詞など、十分に具体的なものであること",
            "  - 良い例: 'Copilot GitHub'、'Cline VSCode'、'LlamaIndex'",
            "  - 悪い例: 'テスト自動化'、'API連携'、'生成AI'",
            "  ※ 上記の例はキーワードの具体性を示すものであり、最新の記事に基づいていないため、そのままは採用しないこと",
            "- 複数のサイトを横断して登場するトピックを優先すること",
            "- 概念的な話題（例: 技術の倫理、社会的影響、経済動向）は除外すること",
        ]

        if exclude:
            formatted_exclude = "\n".join(f"  - {topic}" for topic in exclude)
            prompt_lines.extend(
                [
                    "- 下記の禁止トピックに類似・重複していないこと",
                    formatted_exclude,
                ]
            )

        prompt_lines.extend(
            [
                "",
                "出力形式:",
                "- introduction: トピックの紹介",
                "- query: 検索キーワード(ツール名)",
                "- related_urls: トピックに関連するページのURL(最大5件)",
                "",
                f"出力言語: '{language_code}'",
                "",
                "ページ一覧(JSON):",
                search_results_json,
            ]
        )

        return "\n".join(prompt_lines)

    def select_news_topic(
        self,
        keyword: str,
        language_code: str,
        exclude: list[str] = None,
    ):
        search_results = self.searcher.bulk_search(keyword)

        prompt = self.create_prompt(search_results, language_code, exclude)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=NEWS_TOPIC_SCHEMA,
            ),
        )
        try:
            parsed_result = json.loads(response.text)
            introduction = parsed_result["introduction"]
            query = parsed_result["query"]
            related_urls = parsed_result["related_urls"]
        except Exception as e:
            print(f"Failed to parse news topic response: {e}")
            return "", [], ""

        additional_results = self.searcher.search(query, num_results=10)
        search_results.extend(additional_results)
        additional_urls = [result["url"] for result in additional_results]
        all_urls = list(dict.fromkeys(related_urls + additional_urls))
        selected_urls = all_urls[:5]

        articles = []
        for url in selected_urls:
            matched_article = next(
                (item for item in search_results if item["url"] == url), None
            )
            if not matched_article:
                continue
            title = matched_article["title"]
            body = ArticleContentFetcher.fetch(url)
            articles.append({"title": title, "url": url, "body": body})

        return introduction, articles, query
