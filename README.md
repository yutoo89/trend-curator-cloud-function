Alexa skill [tech-curator](https://github.com/yutoo89/tech-curator/blob/main/README.md)のバックエンドです。

以下のCloud Functionsが含まれます。

1. on_topic_created
2. on_trend_update_started
3. on_user_trend_update_started
4. on_article_created

## on_topic_created

Firestoreにトピックが作成されたときに実行される。

下記のフローでAlexa skillが参照する記事を取得し、Firestoreに保存する。

1. **Web検索**
    - **Custom Search API**を利用して、国内外のエンジニア向け情報サイトから検索を実行
    - キーワードを変えながら検索し、合計30件の検索結果を取得
2. **重要なトピック抽出**
    - 検索結果30件のタイトルを**Gemini**に渡し、特に重要なトピックを抽出
    - 例: 複数の記事で取り上げられたテーマや大手企業のリリースなど
3. **Web検索**
    - **Custom Search API**を利用して抽出したトピックをキーワードに再度検索
4. **記事本文の収集**
    - 検索結果のURLを**BeautifulSoup**でスクレイピングし、本文を収集
5. **記事の要約**
    - 収集された記事のタイトルと本文をFirestoreに保存
    - 今回採用したトピックもFirestoreに保存し、次回の検索から除外

ここで保存した記事をGeminiに渡し、Alexa skillの応答を生成する。

## on_trend_update_started

Cloud Schedulerを使用して、1日1回実行される。

Alexa skillの利用が継続しているユーザに対象を絞り、ニュース更新のPub/Subメッセージを送信する。

## on_user_trend_update_started

ニュース更新のPub/Subメッセージを受信して実行される。

on_topic_createdと同様のフローで記事を取得し、Firestoreに保存する。

