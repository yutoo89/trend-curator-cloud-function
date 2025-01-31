from firebase_admin import firestore
from news import News
from user import User, LANGUAGE_CODE
from question import Question, ANSWER_STATUS


class AlexaHandler:
    @staticmethod
    def play_news(user_id: str, language_code: str, db: firestore.Client):
        """
        ユーザーの言語設定に応じて最新ニュースを取得し、speakとaskを返す
        """
        user_ref = User.collection(db)
        user = User.get_or_create(
            user_ref, user_id=user_id, language_code=language_code
        )
        language = user.language_code

        latest_news = News.get_latest_news(db, language)
        if not latest_news:
            if language == LANGUAGE_CODE["JA"]:
                speak = "本日のニュースは見つかりませんでした。"
                ask = None
            else:
                speak = "No news was found for today."
                ask = None
            return speak, ask

        # speakの生成
        if language == LANGUAGE_CODE["JA"]:
            speak = f"本日のニュースです。{latest_news.content}"
        else:
            speak = f"Here is today's news. {latest_news.content}"

        # askの生成
        if user.get_answer_status(db) == ANSWER_STATUS["READY"]:
            if language == LANGUAGE_CODE["JA"]:
                ask = "以前の質問の回答が保存されています。再生する場合は「回答!」と言ってみてください。"
            else:
                ask = "An answer from your previous question is ready. Say 'Answer!' if you want to hear it."
        else:
            # READY以外の場合
            if language == LANGUAGE_CODE["JA"]:
                ask = (
                    "何か質問がある場合は、「質問!」と宣言した後に質問してみてください。"
                    f"たとえば、「質問! {latest_news.sample_question}」と質問してみてください。"
                )
            else:
                ask = (
                    "If you have any questions, say 'Question!' followed by your query. "
                    f"For example, you could ask: 'Question! {latest_news.sample_question}'"
                )
        return speak, ask

    @staticmethod
    def receive_question(
        user_id: str, language_code: str, question: str, db: firestore.Client
    ):
        """
        質問を受け取り、回答作成を非同期的に開始する（実際の処理は別途）
        """
        user_ref = User.collection(db)
        user = User.get_or_create(
            user_ref, user_id=user_id, language_code=language_code
        )
        language = user.language_code

        # 1. 今日の質問回数が3回以上なら終了
        if user.daily_usage_count >= 3:
            if language == LANGUAGE_CODE["JA"]:
                speak = "本日の質問回数が上限に達しました。また明日ご利用ください。"
            else:
                speak = "You have reached the daily question limit. Please come back tomorrow."
            return speak, None

        # 2. answer_statusがIN_PROGRESSなら終了
        if user.get_answer_status(db) == ANSWER_STATUS["IN_PROGRESS"]:
            if language == LANGUAGE_CODE["JA"]:
                speak = "前回の質問に対する回答を作成中です。もう少々お待ちください。"
            else:
                speak = "Your previous question is still being processed. Please wait a bit longer."
            return speak, None

        # 3. answer_statusがREADYなら終了
        if user.get_answer_status(db) == ANSWER_STATUS["READY"]:
            if language == LANGUAGE_CODE["JA"]:
                speak = "前回の質問に対する回答が準備できています。「回答!」と言ってみてください。"
                ask = "前回の質問に対する回答が準備できています。「回答!」と言ってみてください。"
            else:
                speak = "An answer to your previous question is ready. Say 'Answer!' if you want to hear it."
                ask = "An answer to your previous question is ready. Say 'Answer!' to hear it."
            return speak, ask

        # 4. 新規ドキュメントを作成し、questionフィールドに質問を保存
        user.recreate_question(db=db, question_text=question)

        # ユーザーのステータスを IN_PROGRESS にして保存
        user.daily_usage_count += 1
        user.save(user_ref)

        # 5. 一時応答（回答作成中）を返す
        if language == LANGUAGE_CODE["JA"]:
            speak = "質問を受け付けました。ただいま回答を作成中です。"
            ask = "「回答!」と言ってみてください。回答が作成されていれば再生できます。"
        else:
            speak = "Your question has been received. I'm generating the answer now."
            ask = "Please say 'Answer!' to check if the answer is ready."
        return speak, ask

    @staticmethod
    def answer(user_id: str, language_code: str, db: firestore.Client):
        """
        ユーザーのanswer_statusに応じて適切な応答を返す
        """
        user_ref = User.collection(db)
        user = User.get_or_create(
            user_ref, user_id=user_id, language_code=language_code
        )
        language = user.language_code

        # 日付情報
        answer_status = user.get_answer_status(db)
        speak = ""
        ask = ""

        # 質問がないとき
        if answer_status == ANSWER_STATUS["NO_QUESTION"]:
            if language == LANGUAGE_CODE["JA"]:
                speak = "お預かりしている質問がありません。"
                ask = "質問する場合は、「質問!」と宣言してから質問してみてください。"
            else:
                speak = "No question is being held."
                ask = "If you want to ask a question, please say 'Question!' and then ask your question."
            return speak, ask

        question = user.get_question(db)

        # 回答を作成中のとき
        if answer_status == ANSWER_STATUS["IN_PROGRESS"]:

            if language == LANGUAGE_CODE["JA"]:
                speak = f"現在、質問に対する回答を作成中です。「{question.question_text}」という質問をお預かりしています。もう少々お待ちください。"
                ask = "「回答!」と言ってみてください。回答が作成されていれば再生できます。"
            else:
                speak = f"We're currently preparing an answer to your question. We're holding the question '{question.question_text}'. Please wait a little longer."
                ask = "Please say 'Answer!'. If the answer is ready, it will be played."
            return speak, ask

        # 回答が作成済みのとき
        if answer_status in [
            ANSWER_STATUS["READY"],
            ANSWER_STATUS["ANSWERED"],
        ]:
            if language == LANGUAGE_CODE["JA"]:
                date_str = question.created.strftime("%-m月%-d日")
                speak = f"{date_str}の質問、「{question.question_text}」に対する回答です。「{question.answer_text}」。以上です。"
                ask = "他に質問がある場合は、「質問!」と宣言してから質問してみてください。"
            else:
                date_str = question.created.strftime("%B %-d")
                speak = f"Here is the answer to your question on {date_str}: '{question.question_text}'. '{question.answer_text}'. That is all."
                ask = "If you have any other questions, please say 'Question!' and then ask your question."
            question.answer_status = ANSWER_STATUS["ANSWERED"]
            question_ref = Question.collection(db)
            question.update(question_ref)
            return speak, ask

        question.answer_status = ANSWER_STATUS["ERROR"]
        question_ref = Question.collection(db)
        question.update(question_ref)

        # 回答中にエラーが起きたとき
        if answer_status == ANSWER_STATUS["ERROR"]:
            if language == LANGUAGE_CODE["JA"]:
                speak = "回答の作成中にエラーが発生しました。申し訳ありませんが、もう一度、「質問!」と宣言してから質問をしてみてください。"
                ask = "もう一度、「質問!」と宣言してから質問をしてみてください。"
            else:
                speak = "An error occurred while preparing the answer. Please ask your question again by saying 'Question!'."
                ask = "Please try again. Say 'Question!' and then ask your question."
            return speak, ask

        if language == LANGUAGE_CODE["JA"]:
            speak = "申し訳ありません。予期しないエラーが発生しました。"
            ask = "もう一度、「質問!」と宣言してから質問してみてください。"
        else:
            speak = "I'm sorry. An unexpected error occurred."
            ask = "Please say 'Question!' and then ask your question again."
        return speak, ask
