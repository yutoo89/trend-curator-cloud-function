import os
import re
from vertexai.preview import rag
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
    RAG_CORPUS_NAME = os.getenv("RAG_CORPUS_NAME")
    RAG_CHUNK_SIZE = 512
    RAG_CHUNK_OVERLAP = 100
    RAG_MAX_EMBEDDING_REQUESTS_PER_MIN = 900

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

        json_data = article.to_json()
        blob.upload_from_string(json_data, content_type="application/json")
        print(f"Uploaded article: {article.source} - {article.title}")
        return f"gs://{self.BUCKET_NAME}/{path}"

    def add_to_rag_corpus(self, path: str):
        try:
            rag.import_files(
                self.RAG_CORPUS_NAME,
                [path],
                chunk_size=self.RAG_CHUNK_SIZE,
                chunk_overlap=self.RAG_CHUNK_OVERLAP,
                max_embedding_requests_per_min=self.RAG_MAX_EMBEDDING_REQUESTS_PER_MIN,
            )
        except Exception as e:
            print(f"Failed to import file {path}: {e}")
            raise

    def update_article_body(self, article: Article):
        """Fetch and clean the article body."""
        try:
            article.body = self.content_fetcher.fetch(article.url)
            article.body = self.cleaner.clean_text(article.body)[: self.ARTICLE_MAX_LENGTH]
            article.body = self.cleaner.llm_clean_text(article.body, article.title)
        except Exception as e:
            print(f"[ERROR] Failed to fetch or clean body for URL '{article.url}': {e}")

    def upload_article(self, article: Article):
        """Upload article to GCS and import it to the RAG corpus."""
        gcs_path = self.upload_to_gcs(article)
        self.add_to_rag_corpus(gcs_path)

    def bulk_upload(self):
        articles_by_source = {}

        for source, rss_url in self.RSS_FEEDS.items():
            try:
                articles_by_source[source] = self.fetcher.fetch_articles(
                    rss_url, source
                )
            except Exception as e:
                print(f"[ERROR] Failed to fetch articles for source '{source}': {e}")
                continue

        sources = list(articles_by_source.keys())
        source_article_queues = {
            source: iter(articles) for source, articles in articles_by_source.items()
        }

        total_uploaded = 0
        while True:
            articles_uploaded = False
            for source in sources:
                try:
                    article = next(source_article_queues[source])
                    self.update_article_body(article)

                    try:
                        self.upload_article(article)
                        total_uploaded += 1
                        articles_uploaded = True
                    except Exception:
                        print(f"[ERROR] Failed to process article '{article.url}' from source '{article.source}': {e}")
                        continue

                except StopIteration:
                    # This source has no more articles
                    continue

            if not articles_uploaded:
                # Exit the loop if no articles were uploaded in this round
                break

        print(f"Total articles uploaded: {total_uploaded}")
