from google import genai
from google.genai import types
from services.style import build_prompt
from config import GEMINI_MODEL


# =========================
# Gemini Safety 設定
# =========================
# BLOCK_NONE 只會降低 Gemini API 可調 safety filter 的阻擋門檻，
# 不代表所有系統層限制都會消失。
GEMINI_SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_NONE",
    ),
]


GEMINI_CONFIG = types.GenerateContentConfig(
    safety_settings=GEMINI_SAFETY_SETTINGS
)


def _extract_finish_reason(response):
    """
    只取 Gemini 回覆狀態，不印 prompt / 使用者原文 / AI 回覆原文。
    """
    try:
        candidates = getattr(response, "candidates", None)

        if not candidates:
            return "NO_CANDIDATES"

        first = candidates[0]

        return (
            getattr(first, "finish_reason", None)
            or getattr(first, "finishReason", None)
            or "UNKNOWN"
        )

    except Exception as exc:
        return f"READ_FINISH_REASON_ERROR:{exc}"


def _safe_response_text(response):
    """
    安全取得 response.text。
    某些 safety / empty candidate 情況下，直接讀 response.text 可能是 None 或報錯。
    """
    try:
        text = getattr(response, "text", None)

        if text and str(text).strip():
            return str(text)

    except Exception as exc:
        print("GEMINI response.text read error:", exc)

    return None


# =========================
# 取得 Gemini 回覆
# =========================
def ask_gemini(
    gemini_key,
    history,
    user_text,
    emotion,
    mode="聊天模式",
    chat_persona_settings=None,
    character_settings=None,
    reply_style_settings=None,
    facts=None
):

    # =========================
    # 組 prompt
    # =========================
    prompt = build_prompt(
        history=history,
        user_text=user_text,
        emotion=emotion,
        mode=mode,
        chat_persona_settings=chat_persona_settings,
        character_settings=character_settings,
        reply_style_settings=reply_style_settings,
        facts=facts
    )

    # 不印 prompt 內容，避免解密後的明文進 Render log。
    print("DEBUG prompt built")

    # =========================
    # 呼叫 Gemini
    # =========================
    with genai.Client(api_key=gemini_key) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=GEMINI_CONFIG,
        )

    # 不印 response 內容，避免 AI 回覆明文進 Render log。
    print("DEBUG gemini response received")
    print("GEMINI finish_reason:", _extract_finish_reason(response))

    text = _safe_response_text(response)

    if text:
        return text

    # 不讓 Telegram 因為 None / 空字串直接沉默。
    return "……我剛剛卡了一下，妳再說一次。"


# =========================
# 摘要短期記憶成長期記憶
# =========================
def summarize_memory(gemini_key, chat_text):

    prompt = f"""
你是一個記憶整理AI。

請把以下對話整理成「可長期記憶的事實」。

規則：
- 只保留穩定資訊（習慣、偏好、身份、長期狀態）
- 不要保留閒聊
- 每行一條
- 用 - 開頭

對話：
{chat_text}
"""

    with genai.Client(api_key=gemini_key) as client:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=GEMINI_CONFIG,
        )

    print("DEBUG memory summary received")
    print("GEMINI summary finish_reason:", _extract_finish_reason(response))

    text = _safe_response_text(response)

    if text:
        return text

    return ""
