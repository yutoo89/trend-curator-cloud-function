from typing import List
import feedparser
from article import Article


class RSSArticleFetcher:
    RSS_FEEDS = {
        "Hacker News Latest": "https://hnrss.org/newest",
        "TechCrunch Feed": "https://techcrunch.com/feed/",
        "Dev.to Articles": "https://dev.to/feed",
        "Smashing Magazine Feed": "https://www.smashingmagazine.com/feed/",
        "Stack Overflow Blog Feed": "https://stackoverflow.blog/feed/",
        "Qiita Popular Articles": "https://qiita.com/popular-items/feed.atom",
        "CodeZine Latest Articles": "https://codezine.jp/rss/new/20/index.xml",
    }

    @staticmethod
    def fetch_articles() -> List[Article]:
        articles = []
        for source, url in RSSArticleFetcher.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                print(f"[ERROR] Failed to parse URL '{url}': {e}")
                continue

            for entry in feed.entries:
                try:
                    article = Article.create(
                        source=source,
                        title=entry.title,
                        summary=entry.summary,
                        url=entry.link,
                        published=entry.published,
                    )
                    articles.append(article)
                except Exception as e:
                    print(
                        f"[ERROR] Failed to create article from entry '{entry.title}': {e}"
                    )
                    continue

        return articles
