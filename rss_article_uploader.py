import re
import time
import json
from rss_article_fetcher import RSSArticleFetcher
from google.cloud import storage
from article import Article
from article_cleaner import ArticleCleaner
from article_content_fetcher import ArticleContentFetcher


class RssArticleUploader:
    BUCKET_NAME = "trend-curator-articles"
    ARTICLE_MAX_LENGTH = 3000
    RSS_FEEDS = {
        "Hacker News Latest": "https://hnrss.org/newest",
        "TechCrunch Feed": "https://techcrunch.com/feed/",
        "Dev.to Articles": "https://dev.to/feed",
        "Smashing Magazine Feed": "https://www.smashingmagazine.com/feed/",
        "Stack Overflow Blog Feed": "https://stackoverflow.blog/feed/",
        "Qiita Popular Articles": "https://qiita.com/popular-items/feed.atom",
        "CodeZine Latest Articles": "https://codezine.jp/rss/new/20/index.xml",
    }

    def __init__(self, model_name: str):
        self.fetcher = RSSArticleFetcher(model_name)
        self.content_fetcher = ArticleContentFetcher
        self.cleaner = ArticleCleaner(model_name)
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
        print(f"Uploaded article: {article.source} - {article.title}")

    def bulk_upload(self):
        articles_by_source = {
            source: self.fetcher.fetch_articles(rss_url, source)
            for source, rss_url in self.RSS_FEEDS.items()
        }

        sources = list(articles_by_source.keys())
        source_article_queues = {
            source: iter(articles) for source, articles in articles_by_source.items()
        }

        while True:
            articles_uploaded = False
            for source in sources:
                try:
                    article = next(source_article_queues[source])
                    try:
                        article.body = self.content_fetcher.fetch(article.url)
                        time.sleep(2)
                        article.body = self.cleaner.clean_text(article.body)[
                            : self.ARTICLE_MAX_LENGTH
                        ]
                        article.body = self.cleaner.llm_clean_text(
                            article.body, article.title
                        )
                    except Exception as e:
                        print(f"[ERROR] Failed to fetch URL '{article.url}': {e}")

                    self.upload_to_gcs(article)
                    articles_uploaded = True
                except StopIteration:
                    # This source has no more articles
                    continue

            if not articles_uploaded:
                # Exit the loop if no articles were uploaded in this round
                break
