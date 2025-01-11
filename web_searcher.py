from googleapiclient.discovery import build


class WebSearcher:
    def __init__(self, google_custom_search_api_key: str, google_search_cse_id: str):
        self.api_key = google_custom_search_api_key
        self.cse_id = google_search_cse_id
        self.service = build("customsearch", "v1", developerKey=self.api_key)

    def search(self, query: str, exclude_keywords=None, num_results: int = 10):
        if exclude_keywords is None:
            exclude_keywords = []

        # -keyword で除外指定
        for ek in exclude_keywords:
            query += f" -{ek}"

        result = (
            self.service.cse()
            .list(
                q=query,
                cx=self.cse_id,
                dateRestrict="w2",  # 過去4週間
                num=num_results,
            )
            .execute()
        )

        items = result.get("items", [])
        search_results = [
            {"rank": i + 1, "title": item["title"], "url": item["link"]}
            for i, item in enumerate(items)
        ]
        return search_results
