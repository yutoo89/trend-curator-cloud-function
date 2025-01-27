from typing import List
import feedparser
from article import Article
from article_cleaner import ArticleCleaner


class RSSArticleFetcher:
    FEED_ENTRIES_LIMIT = 10

    def __init__(self, model_name: str):
        self.cleaner = ArticleCleaner(model_name)

    def fetch_articles(self, rss_url: str, source: str = None) -> List[Article]:
        articles = []

        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"[ERROR] Failed to parse URL '{rss_url}': {e}")
            return []

        for entry in feed.entries[: self.FEED_ENTRIES_LIMIT]:
            title = entry.title
            summary = self.cleaner.clean_text(entry.summary)
            article = Article(
                source=source,
                title=title,
                summary=summary,
                url=entry.link,
                published=entry.published,
            )
            articles.append(article)

        return articles
