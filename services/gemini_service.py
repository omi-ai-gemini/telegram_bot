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
    safety_settings=GEMINI_SAFETY_SETTINGS,
    # 降低候選回覆飄到敏感方向的機率。
    temperature=0.4,
    max_output_tokens=512,
)


def _enum_name(value):
    """
    把 Gemini SDK 回傳的 Enum / 物件安全轉成可讀文字。
    不印 prompt 明文，不印 AI 回覆明文。
    """
    if value is None:
        return None

    return getattr(value, "name", str(value))


def _read_attr(obj, *names):
    """
    同時相容 snake_case / camelCase 欄位名稱。
    """
    if obj is None:
        return None

    for name in names:
        value = getattr(obj, name, None)

        if value is not None:
            return value

    return None


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
            _read_attr(first, "finish_reason", "finishReason")
            or "UNKNOWN"
        )

    except Exception as exc:
        return f"READ_FINISH_REASON_ERROR:{exc}"


def debug_gemini_response(response, label="GEMINI"):
    """
    印出 Gemini 空回覆可追查的原因。

    重點：
    - 不印 prompt 明文
    - 不印 AI 回覆明文
    - 只印 block reason / safety rating / parts 數量 / text 長度
    """
    print(f"========== {label} DEBUG START ==========")

    usage = _read_attr(response, "usage_metadata", "usageMetadata")

    if usage:
        print(f"{label} usage_metadata:", usage)

    feedback = _read_attr(response, "prompt_feedback", "promptFeedback")

    if feedback:
        block_reason = _read_attr(feedback, "block_reason", "blockReason")
        print(f"{label} prompt_block_reason:", _enum_name(block_reason))

        safety_ratings = _read_attr(feedback, "safety_ratings", "safetyRatings") or []

        if not safety_ratings:
            print(f"{label} prompt_safety_ratings: EMPTY")

        for rating in safety_ratings:
            print(
                f"{label} prompt_safety:",
                "category=", _enum_name(_read_attr(rating, "category")),
                "probability=", _enum_name(_read_attr(rating, "probability")),
                "blocked=", _read_attr(rating, "blocked"),
            )
    else:
        print(f"{label} prompt_feedback: None")

    candidates = getattr(response, "candidates", None)

    if not candidates:
        print(f"{label} candidates: EMPTY")
        print(f"========== {label} DEBUG END ==========")
        return

    print(f"{label} candidates_count:", len(candidates))

    for index, candidate in enumerate(candidates):
        finish_reason = _read_attr(candidate, "finish_reason", "finishReason")
        print(f"{label} candidate[{index}] finish_reason:", _enum_name(finish_reason))

        safety_ratings = _read_attr(candidate, "safety_ratings", "safetyRatings") or []

        if not safety_ratings:
            print(f"{label} candidate[{index}] safety_ratings: EMPTY")

        for rating in safety_ratings:
            print(
                f"{label} candidate[{index}] safety:",
                "category=", _enum_name(_read_attr(rating, "category")),
                "probability=", _enum_name(_read_attr(rating, "probability")),
                "blocked=", _read_attr(rating, "blocked"),
            )

        content = getattr(candidate, "content", None)

        if not content:
            print(f"{label} candidate[{index}] content: None")
            continue

        parts = getattr(content, "parts", None) or []
        print(f"{label} candidate[{index}] parts_count:", len(parts))

        for part_index, part in enumerate(parts):
            text = getattr(part, "text", None)

            if text is None:
                print(f"{label} candidate[{index}] part[{part_index}] text: None")
            else:
                print(
                    f"{label} candidate[{index}] part[{part_index}] text_length:",
                    len(str(text)),
                )

    print(f"========== {label} DEBUG END ==========")


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
    print("GEMINI finish_reason:", _enum_name(_extract_finish_reason(response)))
    debug_gemini_response(response, label="GEMINI")

    text = _safe_response_text(response)

    if text:
        return text

    # Gemini 沒有可用文字時，不回傳假角色訊息。
    # 讓 run_ai 不寫入記憶、不傳送假回覆；原因看上面的 GEMINI DEBUG。
    print("GEMINI empty reply: no text returned")
    return None


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
    print("GEMINI summary finish_reason:", _enum_name(_extract_finish_reason(response)))
    debug_gemini_response(response, label="GEMINI SUMMARY")

    text = _safe_response_text(response)

    if text:
        return text

    return ""
