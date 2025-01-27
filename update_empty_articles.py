import os
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from article import Article
from article_cleaner import ArticleCleaner
import google.generativeai as genai

# GenAI 初期化
genai.configure(api_key=os.environ["GENAI_API_KEY"])

# Firebase初期化
if not firebase_admin._apps:
    firebase_admin.initialize_app()

# Firestoreクライアントの取得
db = firestore.client()
cleaner_instance = ArticleCleaner("gemini-1.5-flash")

# Articleクラスのコレクション参照の取得
article_collection = Article.collection(db)

cnt = 0
body_query = article_collection.where(filter=FieldFilter("body", "in", [None, ""]))
for doc in body_query.stream():
    cnt += 1
    article = Article.from_dict(doc.to_dict())
    print(f"Processing article with empty or missing body: ID {article.title}")
    article.import_body(article_collection, cleaner_instance)  # cleaner_instanceは適切に定義する必要がある

print(f"Updated {cnt} article body.")

cnt = 0
embedding_query = article_collection.where(filter=FieldFilter("embedding", "==", None))
for doc in embedding_query.stream():
    cnt += 1
    article = Article.from_dict(doc.to_dict())
    print(f"Processing article with missing embedding: ID {article.title}")
    article.vectorize(article_collection)

print(f"Updated {cnt} article embedding.")
