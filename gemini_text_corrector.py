import json
import google.generativeai as genai
import typing_extensions as typing


RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "original_text": {"type": "STRING"},
        "transformed_text": {"type": "STRING"},
    },
    "required": ["original_text", "transformed_text"],
}


class GeminiTextCorrector:
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)

    def create_prompt(self, input_text: str, region_code: str) -> str:
        lines = [
            "以下の指示に従い、提供された文字列を修正してください。",
            "- text, region_codeが提供されます",
            "- textは誤字や欠損を含む可能性のある文字列なので、元の単語を推測して正しい表記に変換してください",
            "- textが多義語である場合は、region_codeが示す地域における最も一般的な解釈を正解として、他の意味と混同しないように補足を加えてください",
            "- textに誤りがない場合はそのままの形で出力してください\n",
            "例1:",
            "- input: {text: '生成 エーアイ', region_code: 'JP'}",
            "- output: '生成AI'",
            "例2:",
            "- input: {text: 'hyde', region_code: 'JP'}",
            "- output: '歌手のhyde'\n",
            "提供する情報:",
            f"- text: {input_text}",
            f"- region_code: {region_code}",
        ]
        return "\n".join(lines)

    def run(self, input_text: str, region_code: str) -> str:
        prompt = self.create_prompt(input_text, region_code)
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
        parsed_result = json.loads(response.text)
        return parsed_result["transformed_text"]
