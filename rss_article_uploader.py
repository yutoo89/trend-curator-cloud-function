import time
from rss_article_fetcher import RSSArticleFetcher
from article import Article
from article_cleaner import ArticleCleaner
from article_content_fetcher import ArticleContentFetcher
from firebase_admin import firestore


class RssArticleUploader:
    BUCKET_NAME = "trend-curator-articles"
    ARTICLE_MAX_LENGTH = 3000
    EMBEDDING_MODEL = "models/text-embedding-004"
    RSS_FEEDS = {
        "Hacker News Latest": "https://hnrss.org/newest",
        "TechCrunch Feed": "https://techcrunch.com/feed/",
        "Dev.to Articles": "https://dev.to/feed",
        "Smashing Magazine Feed": "https://www.smashingmagazine.com/feed/",
        "Stack Overflow Blog Feed": "https://stackoverflow.blog/feed/",
        "Qiita Popular Articles": "https://qiita.com/popular-items/feed.atom",
        "CodeZine Latest Articles": "https://codezine.jp/rss/new/20/index.xml",
    }

    def __init__(self, model_name: str, db: firestore.Client):
        self.fetcher = RSSArticleFetcher(model_name)
        self.content_fetcher = ArticleContentFetcher
        self.cleaner = ArticleCleaner(model_name)
        self.article_collection = db.collection(Article.COLLECTION_NAME)

    def update_article_body(self, article: Article):
        """Fetch and clean the article body."""
        try:
            article.body = self.content_fetcher.fetch(article.url)
            article.body = self.cleaner.clean_text(article.body)[
                : self.ARTICLE_MAX_LENGTH
            ]
            article.body = self.cleaner.llm_clean_text(article.body, article.title)
        except Exception as e:
            print(f"[ERROR] Failed to fetch or clean body for URL '{article.url}': {e}")

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

                    try:
                        doc_id = article.id()
                        doc_ref = self.article_collection.document(doc_id)
                        if doc_ref.get().exists:
                            print(
                                f"[INFO] Article '{article.title}' already exists. Skipping upload."
                            )
                            continue

                        self.update_article_body(article)
                        time.sleep(2)
                        article = article.vectorize(model_name=self.EMBEDDING_MODEL)
                        article.save(doc_ref)
                        total_uploaded += 1
                        articles_uploaded = True
                        print(
                            f"[INFO] Vectorization successful for title: {article.title}"
                        )
                    except Exception as e:
                        print(
                            f"[ERROR] Failed to process article '{article.url}' from source '{article.source}': {e}"
                        )
                        continue

                except StopIteration:
                    # This source has no more articles
                    continue

            if not articles_uploaded:
                # Exit the loop if no articles were uploaded in this round
                break

        print(f"Total articles uploaded: {total_uploaded}")
