import requests
from bs4 import BeautifulSoup


class ArticleContentFetcher:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    @staticmethod
    def fetch(url: str):
        try:
            response = requests.get(url, headers=ArticleContentFetcher.HEADERS, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            return "".join([p.get_text().strip() for p in paragraphs])
        except Exception as e:
            print(f"Failed to fetch article from {url}: {e}")
            return ""
