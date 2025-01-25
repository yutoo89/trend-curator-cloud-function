from __future__ import annotations
from datetime import datetime
import json


class Article:
    COLLECTION_NAME = "articles"

    def __init__(
        self,
        source: str,
        title: str,
        summary: str,
        body: str,
        url: str,
        published: datetime,
    ):
        if not isinstance(published, datetime):
            published = datetime.now()
        self.source = source
        self.title = title
        self.summary = summary
        self.body = body
        self.url = url
        self.published = published

    def to_json(self):
        data = {
            "url": self.url,
            "published": self.published.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
        }
        return json.dumps(data, ensure_ascii=False)
