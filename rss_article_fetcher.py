from typing import List
import feedparser
from article import Article
from article_cleaner import ArticleCleaner
from article_content_fetcher import ArticleContentFetcher


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
        cleaner = ArticleCleaner("gemini-1.5-flash")
        for source, url in RSSArticleFetcher.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                print(f"[ERROR] Failed to parse URL '{url}': {e}")
                continue

            for entry in feed.entries:
                title = entry.title
                summary = cleaner.clean_text(entry.summary)
                try:
                    body = ArticleContentFetcher.fetch(entry.link)
                    body = cleaner.clean_text(body)
                    body = cleaner.llm_clean_text(body, title)
                except Exception as e:
                    body = ""
                article = Article(
                        source=source,
                    title=title,
                    summary=summary,
                    body=body,
                        url=entry.link,
                        published=entry.published,
                    )
                    articles.append(article)

        return articles
