from __future__ import annotations
from firebase_admin import firestore
from related_keyword_generator import RelatedKeywordGenerator
from web_searcher import WebSearcher
from trend_topic_selector import TrendTopicSelector
from article_content_fetcher import ArticleContentFetcher
from tip_generator import TipGenerator


class Trend:
    def __init__(self, user_id: str, title: str, body: str, keywords: list[str]):
        self.user_id = user_id
        self.title = title
        self.body = body
        self.keywords = keywords

    @staticmethod
    def update(
        db: firestore.Client,
        user_id: str,
        topic: str,
        language_code: str,
        searcher: WebSearcher,
        exclude_keywords=None,
    ) -> Trend:
        print("[INFO] Trend.update - Start processing")

        query = topic
        if exclude_keywords is None:
            exclude_keywords = []

        # 関連キーワード生成
        print("[INFO] Generating related keywords - Start")
        keywords_generator = RelatedKeywordGenerator("gemini-1.5-flash")
        related_keywords = keywords_generator.generate_keywords(query)
        print(f"[INFO] Generating related keywords - Done: {related_keywords}")

        # キーワードweb検索
        print("[INFO] Performing web search - Start")
        all_results = []
        for keyword in [query] + related_keywords:
            results = searcher.search(
                keyword, exclude_keywords=exclude_keywords, num_results=10
            )
            all_results.extend(results)
        print(
            f"[INFO] Performing web search - Done: {len(all_results)} results found"
        )

        # 検索結果からトレンドトピックを抽出
        print("[INFO] Selecting trend topic - Start")
        selector = TrendTopicSelector("gemini-1.5-flash")
        selected_topic, related_urls, extracted_keywords = selector.select_trend_topic(
            query, all_results, exclude_keywords, language_code
        )
        print(
            f"[INFO] Selecting trend topic - Done: {selected_topic}, extracted_keywords: {extracted_keywords}"
        )

        # 関連ページの本文を取得
        print("[INFO] Fetching article contents - Start")
        fetcher = ArticleContentFetcher()
        articles_to_fetch = related_urls[:3]
        articles = []
        for url in articles_to_fetch:
            content = fetcher.fetch(url)
            articles.append({"url": url, "body": content[:3000]})  # 例: 文字数上限
        print(
            f"[INFO] Fetching article contents - Done: {len(articles)} articles fetched"
        )

        # 要約生成
        print("[INFO] Generating manuscript - Start")
        generator = TipGenerator("gemini-1.5-flash")
        manuscript = generator.run(selected_topic, articles, language_code)
        print(f"[INFO] Generating manuscript - Done\n[INFO] Manuscript: {manuscript}")

        # Firestore に保存
        doc_ref = db.collection("trends").document(user_id)
        doc_ref.set(
            {
                "title": selected_topic,
                "body": manuscript,
                "keywords": extracted_keywords,
            },
            merge=True,
        )

        return Trend(user_id, selected_topic, manuscript, extracted_keywords)
