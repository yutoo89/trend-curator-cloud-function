import json
import google.generativeai as genai
import typing_extensions as typing


class CorrectorResult(typing.TypedDict):
    original_text: str
    transformed_text: str


class GeminiTextCorrector:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, input_text: str) -> str:
        lines = [
            f"音声認識で「{input_text}」というテキストが得られました。",
            "このテキストは誤字や欠損がある可能性があるので、元の単語を推測して広く知られる正しい表記に変換してください。",
            "テキストに誤りがない場合はそのままの形で出力してください。",
            "例:",
            "- input: `生成 エーアイ`",
            "- output: `生成AI`",
        ]
        return "\n".join(lines)

    def run(self, input_text: str) -> str:
        prompt = self.create_prompt(input_text)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[CorrectorResult],
            ),
        )
        return json.loads(response.text)[0]["transformed_text"]
