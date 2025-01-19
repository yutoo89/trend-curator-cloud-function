from googleapiclient.discovery import build


class WebSearcher:
    TARGET_SITES = [
        "codezine.jp",
        "news.ycombinator.com",
        "atmarkit.itmedia.co.jp",
        "qiita.com",
    ]

    SEARCH_MODIFIERS = ["release", "use", "tips"]

    def __init__(self, google_custom_search_api_key: str, google_search_cse_id: str):
        self.api_key = google_custom_search_api_key
        self.cse_id = google_search_cse_id
        self.service = build("customsearch", "v1", developerKey=self.api_key)

    def search(self, query: str, num_results: int = 10):
        result = (
            self.service.cse()
            .list(
                q=query,
                cx=self.cse_id,
                dateRestrict="w2",  # 過去2週間
                num=num_results,
            )
            .execute()
        )

        items = result.get("items", [])
        search_results = [
            {"title": item["title"], "url": item["link"]} for item in items
        ]
        return search_results

    def bulk_search(self, keyword: str):
        all_results = []

        site_filter = " OR ".join([f"site:{site}" for site in self.TARGET_SITES])

        for modifier in self.SEARCH_MODIFIERS:
            query = f"{site_filter} {keyword} {modifier}"
            results = self.search(query, num_results=10)
            all_results.extend(results)

        return all_results
