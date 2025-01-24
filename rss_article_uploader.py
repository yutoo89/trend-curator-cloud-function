import re
import json
from rss_article_fetcher import RSSArticleFetcher
from google.cloud import storage
from article import Article


class RssArticleUploader:
    BUCKET_NAME = "trend-curator-articles"
    RSS_FEEDS = {
        "Hacker News Latest": "https://hnrss.org/newest",
        "TechCrunch Feed": "https://techcrunch.com/feed/",
        "Dev.to Articles": "https://dev.to/feed",
        # "Smashing Magazine Feed": "https://www.smashingmagazine.com/feed/", # 本文取れない
        # "Stack Overflow Blog Feed": "https://stackoverflow.blog/feed/", # 本文取れない
        "Qiita Popular Articles": "https://qiita.com/popular-items/feed.atom",
        "CodeZine Latest Articles": "https://codezine.jp/rss/new/20/index.xml",
    }

    def __init__(self, model_name: str):
        self.fetcher = RSSArticleFetcher(model_name)
        self.gcs = storage.Client()
        self.bucket = self.gcs.bucket(self.BUCKET_NAME)

    def upload_to_gcs(self, article: Article):
        """Upload a file to Google Cloud Storage."""
        safe_url = re.sub(
            r"[^\w\-]", "_", article.url.replace("https://", "").replace("http://", "")
        )
        path = f"{safe_url}.json"
        blob = self.bucket.blob(path)

        json_data = json.dumps(article.to_dict(), ensure_ascii=False, indent=4)
        blob.upload_from_string(json_data, content_type="application/json")
        print(f"File {path} uploaded.")

    def bulk_upload(self):
        for source, rss_url in self.RSS_FEEDS.items():
            articles = self.fetcher.fetch_articles(rss_url, source)
            print(f"Found {len(articles)} articles from {source}")
            for article in articles:
                self.upload_to_gcs(article)
