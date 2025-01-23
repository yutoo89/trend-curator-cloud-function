import requests
from bs4 import BeautifulSoup


class ArticleContentFetcher:
    @staticmethod
    def fetch(url: str):
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            return "".join([p.get_text().strip() for p in paragraphs])
        except Exception as e:
            print(f"Failed to fetch article from {url}: {e}")
            return ""
