from __future__ import annotations
from datetime import datetime, timezone
from firebase_admin import firestore
from related_keyword_generator import RelatedKeywordGenerator
from web_searcher import WebSearcher
from trend_topic_selector import TrendTopicSelector
from article_content_fetcher import ArticleContentFetcher
from tip_generator import TipGenerator
from topic import Topic


class Trend:
    MONTHLY_LIMIT = 100

    def __init__(
        self,
        user_id: str,
        title: str,
        topic: str,
        body: str,
        keywords: list[str],
        queries: list[str] = None,
    ):
        if queries is None:
            queries = []
        self.user_id = user_id
        self.title = title
        self.topic = topic
        self.body = body
        self.keywords = keywords
        self.queries = queries

    @staticmethod
    def update(
        db: firestore.Client,
        user_id: str,
        topic: Topic,
        searcher: WebSearcher,
    ) -> Trend:
        print("[INFO] Trend.update - Start processing")

        query = topic.topic
        language_code = topic.language_code
        exclude_keywords = topic.exclude_keywords
        exclude_queries = topic.queries

        # 関連キーワード生成
        print("[INFO] Generating related keywords - Start")
        keywords_generator = RelatedKeywordGenerator("gemini-1.5-flash")
        related_keywords = keywords_generator.generate_keywords(query, exclude_queries)
        print(f"[INFO] Generating related keywords - Done: {related_keywords}")

        # キーワードweb検索
        print("[INFO] Performing web search - Start")
        all_results = []
        for keyword in [query] + related_keywords:
            results = searcher.search(
                keyword, exclude_keywords=exclude_keywords, num_results=10
            )
            all_results.extend(results)
        print(f"[INFO] Performing web search - Done: {len(all_results)} results found")

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
                "topic": query,
                "body": manuscript,
                "keywords": extracted_keywords,
                "queries": related_keywords,
            },
            merge=True,
        )

        return Trend(user_id, selected_topic, query, manuscript, extracted_keywords)

    @staticmethod
    def reset_usage(db: firestore.Client, user_id: str):
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = db.collection("trends").document(user_id)

        doc_ref.set(
            {
                "monthly_usage": 0,
                "remaining_usage": Trend.MONTHLY_LIMIT,
                "last_reset_date": now,
            },
            merge=True,
        )

    @staticmethod
    def increment_usage(db: firestore.Client, user_id: str):
        doc_ref = db.collection("trends").document(user_id)
        doc = doc_ref.get()

        if doc.exists:
            trend_data = doc.to_dict()
            monthly_usage = trend_data.get("monthly_usage", 0)
            remaining_usage = trend_data.get("remaining_usage", Trend.MONTHLY_LIMIT)

            if remaining_usage <= 0:
                print(f"[INFO] User {user_id} has reached the monthly limit.")
                return False

            monthly_usage += 1
            remaining_usage -= 1

            doc_ref.set(
                {"monthly_usage": monthly_usage, "remaining_usage": remaining_usage},
                merge=True,
            )
            return True

        else:
            print(
                f"[INFO] No trend data found for user {user_id}, initializing counters."
            )
            doc_ref.set(
                {
                    "monthly_usage": 1,
                    "remaining_usage": Trend.MONTHLY_LIMIT - 1,
                    "last_reset_date": datetime.now(timezone.utc).isoformat(),
                },
                merge=True,
            )
            return True
