from google import genai
from google.genai import types

TEST_GEMINI_BLOCKED = "__TEST_GEMINI_BLOCKED__"


TEST_SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
]


def _safe_response_text(response):
    try:
        text = response.text
        if text:
            return str(text).strip()
    except Exception:
        pass

    try:
        parts = response.candidates[0].content.parts
        values = []
        for part in parts:
            value = getattr(part, "text", None)
            if value:
                values.append(str(value))
        return "\n".join(values).strip()
    except Exception:
        return ""


def ask_test_gemini(api_key, prompt, model="gemini-3.1-flash-lite", temperature=0.7, max_output_tokens=768):
    """Prompt Tuner 專用 Gemini 呼叫，不走主遊戲 services.gemini_service。"""
    if not api_key:
        return ""

    try:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            safety_settings=TEST_SAFETY_SETTINGS,
            temperature=float(temperature or 0.7),
            max_output_tokens=int(max_output_tokens or 768),
        )

        response = client.models.generate_content(
            model=str(model or "gemini-3.1-flash-lite"),
            contents=prompt,
            config=config,
        )

        text = _safe_response_text(response)
        if not text:
            return TEST_GEMINI_BLOCKED

        return text

    except Exception as exc:
        print("TEST LAB GEMINI ERROR:", exc, flush=True)
        return ""
