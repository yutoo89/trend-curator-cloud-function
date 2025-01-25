import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1.vector import Vector
import google.generativeai as genai
import datetime


TIP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "manuscript": {"type": "STRING"},
    },
    "required": ["manuscript"],
}
EMBEDDING_MODEL = "models/text-embedding-004"


class RAGNewsAgent:
    def __init__(self, model_name, db: firestore.Client):
        self.db = db
        self.gemini_model = genai.GenerativeModel(model_name)

    def _search_articles(self, query_vector, top_k=10):
        collection = self.db.collection("articles")

        vector_query = collection.select(
            ["title", "summary", "body", "url", "published"]
        ).find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.EUCLIDEAN,
            limit=top_k,
        )
        articles = []
        for doc in vector_query.stream():
            articles.append(self._convert_firestore_document(doc.to_dict()))

        return articles

    def _convert_firestore_document(self, doc_dict):
        """
        Firestoreのドキュメントをシリアライズ可能な形式に変換するヘルパー関数。
        タイムスタンプを文字列に変換する。
        """
        for key, value in doc_dict.items():
            if isinstance(value, DatetimeWithNanoseconds):
                doc_dict[key] = value.isoformat()
            elif isinstance(value, datetime.datetime):
                doc_dict[key] = value.isoformat()
        return doc_dict

    def _create_prompt(self, topic, articles, language_code):
        articles_json = json.dumps(articles, ensure_ascii=False)
        print("articles_json:", articles_json)
        prompt_lines = [
            "話題になっているトピックと関連記事を提供します。",
            "第三者視点でこのトピックを紹介するニュース原稿を250文字以内で作成してください。",
            "- 抽象的・定性的な表現は省略し、ソフトウェアエンジニアの業務に役立つ具体的なTipsを作成します",
            "- タイトルの内容の簡潔な説明を冒頭に含め、記事を俯瞰する視点から解説します",
            "  - 例: 「~という記事が注目されています」「〜が話題となっています」",
            "- ソフトウェアエンジニアの業務に役立つTipsを含めます",
            "  - 例: 現在主流となっている類似のサービスとの比較、ベースとなった技術の解説",
            "- 抽象的・曖昧な表現は避け、固有名詞や具体例を多用します",
            "- 作成した原稿をそのままニュースとして読み上げても違和感のない表現にします",
            f"- 原稿は'{language_code}'(language_code)で作成します",
            "",
            f"トピック: {topic}",
            "関連記事(JSON):",
            articles_json,
        ]
        return "\n".join(prompt_lines)

    def _generate_response(self, topic, articles, language_code):
        prompt = self._create_prompt(topic, articles, language_code)
        response = self.gemini_model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=TIP_SCHEMA,
            ),
        )
        try:
            manuscript = json.loads(response.text)["manuscript"]
            return manuscript
        except Exception as e:
            print(f"Failed to parse summary response: {e}")
            return {}

    def generate_response(self, topic, query, language_code="ja"):
        query_vector = genai.embed_content(model=EMBEDDING_MODEL, content=query)[
            "embedding"
        ]
        articles = self._search_articles(query_vector)
        if not articles:
            return "該当する記事が見つかりませんでした。"
        return self._generate_response(topic, articles, language_code)


# # Example Usage
# import firebase_admin
# from firebase_admin import firestore

# # GenAI 初期化
# genai.configure(api_key=os.environ["GENAI_API_KEY"])

# # Firestore 初期化
# if not firebase_admin._apps:
#     firebase_admin.initialize_app()
# db = firestore.client()

# agent = RAGNewsAgent("gemini-1.5-flash", db)
# query = "最近のおすすめのAIツールは？"
# response = agent.generate_response(
#     "tst",
#     query,
# )
# print("Generated Response:", response)
