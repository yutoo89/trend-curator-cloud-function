from rss_article_fetcher import RSSArticleFetcher
from article import Article
from firebase_admin import firestore


class RssArticleUploader:
    BUCKET_NAME = "trend-curator-articles"
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
        self.article_collection = Article.collection(db)

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
        # 同じサイトに連続でアクセスするとスクレイピングが失敗するため順番を入れ替える
        while True:
            articles_uploaded = False
            for source in sources:
                try:
                    article = next(source_article_queues[source])

                    try:
                        doc_id = article.id
                        if Article.exists(self.article_collection, doc_id):
                            print(
                                f"[INFO] Article '{article.title}' already exists. Skipping upload."
                            )
                            continue
                        article.save(self.article_collection)
                        total_uploaded += 1
                        articles_uploaded = True
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


# import os
# import firebase_admin
# from firebase_admin import firestore
# import google.generativeai as genai

# genai.configure(api_key=os.environ["GENAI_API_KEY"])
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# uploader = RssArticleUploader("gemini-1.5-flash", db)
# id = "careers_arsenal_com_jobs_5434108-research-engineer"
# uploader.bulk_upload()
