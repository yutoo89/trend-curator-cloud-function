Alexa skill [tech-curator](https://github.com/yutoo89/tech-curator/blob/main/README.md)のバックエンドです。

以下のCloud Functionsが含まれます。

1. on_trend_update_started
2. on_article_created

## on_trend_update_started

Cloud Schedulerによって1日1回トリガーされる。

国内外のニュースサイトからRSSフィードを通じて記事タイトルとURLを収集し、Firestoreに保存する。

また、直近に収集した記事のタイトルから特に重要なトピックをGeminiで選定し、その日のニュース音声を作成する。

## on_article_created

Firestoreに記事が保存されたことによってトリガーされる。

以下2つの処理が実行される。

### 1. 記事本文の取得と整形

記事のURLにアクセスし、BeautifulSoupを使用して本文を抽出する。

抽出した本文に対して、Geminiを使用して広告文や無関係の話題などのノイズを処理する。

Firestoreの記事情報を、整形後の本文を使用して更新する。

### 2. 記事内容のベクトル化

RSSフィードとスクレイピングを通じて得られた記事情報を、Geminiのembeddingモデルを使用してベクトル化する。

Firestoreにベクトルを保存し、ユーザーから質問を受けた際にRAG(検索拡張生成)を使用して回答を生成する。
