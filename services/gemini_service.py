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


# =========================
# Gemini 阻擋狀態標記
# =========================
# 讓呼叫端可以分辨：
# - 一般聊天被安全層擋下 → 回聊天室「內容被安全阻擋」
# - 摘要任務被安全層擋下 → 回聊天室「摘要長期記憶時被阻擋」
GEMINI_BLOCKED = "__GEMINI_BLOCKED__"
MEMORY_SUMMARY_BLOCKED = "__MEMORY_SUMMARY_BLOCKED__"


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


def get_gemini_block_reason(response):
    """
    判斷 Gemini 是否因安全層阻擋而沒有產生可用內容。

    回傳：
    - None：沒有明確阻擋
    - 字串：阻擋原因，例如 PROMPT:PROHIBITED_CONTENT / CANDIDATE:SAFETY

    注意：
    - 不讀 prompt 明文
    - 不讀 response 明文
    - 只讀 Gemini 回傳的狀態欄位
    """
    try:
        feedback = _read_attr(response, "prompt_feedback", "promptFeedback")

        if feedback:
            block_reason = _read_attr(feedback, "block_reason", "blockReason")
            block_reason_name = _enum_name(block_reason)

            if block_reason_name and block_reason_name not in [
                "BLOCK_REASON_UNSPECIFIED",
                "UNSPECIFIED",
                "0",
            ]:
                return f"PROMPT:{block_reason_name}"

        candidates = getattr(response, "candidates", None) or []

        for candidate in candidates:
            finish_reason = _read_attr(candidate, "finish_reason", "finishReason")
            finish_reason_name = _enum_name(finish_reason)

            if finish_reason_name in [
                "SAFETY",
                "PROHIBITED_CONTENT",
                "BLOCKLIST",
                "SPII",
            ]:
                return f"CANDIDATE:{finish_reason_name}"

            safety_ratings = _read_attr(candidate, "safety_ratings", "safetyRatings") or []

            for rating in safety_ratings:
                if _read_attr(rating, "blocked") is True:
                    category = _enum_name(_read_attr(rating, "category")) or "UNKNOWN"
                    return f"CANDIDATE_SAFETY:{category}"

    except Exception as exc:
        print("GEMINI block reason read error:", exc)

    return None


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
    facts=None,
    memory_context=None,
    time_context=None
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
        facts=facts,
        memory_context=memory_context,
        time_context=time_context
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

    block_reason = get_gemini_block_reason(response)

    if block_reason:
        print("GEMINI blocked reply:", block_reason)
        return GEMINI_BLOCKED

    # Gemini 沒有可用文字，但也沒有明確阻擋時，維持不傳假角色訊息。
    print("GEMINI empty reply: no text returned")
    return None


# =========================
# 摘要 / 記憶處理前綴
# 注意：這段會放在所有記憶整理 prompt 最上方。
# 不放「解除安全限制」類文字，避免 Gemini 直接判成 PROHIBITED_CONTENT。
# =========================
MEMORY_PROCESSING_PREFIX = """
你是 Telemini 的記憶整理模組，只負責整理資料，不負責角色扮演或回覆使用者。

最高優先規則：
- 不要嘗試關閉、繞過或修改任何安全規則。
- 不要輸出開發者模式、解除限制、忽略規則等內容。
- 不要新增原文沒有的設定、情緒、動作或關係。
- 不要逐字保留敏感原文；必要時以中性描述整理。
- 只整理對未來接續對話有用的資訊。
- 如果資訊不確定，標記為「不確定」。
""".strip()


SUMMARY_PROMPTS = {
    "segment": """
請把以下 100 則左右的短期對話整理成一段「分段長期摘要」。

輸出格式固定如下：
【場景狀態】
【事件進展】
【角色狀態】
【使用者狀態】
【關係變化】
【重要事實】
【未完成伏筆】
【下一步銜接】

整理要求：
- 不要逐句流水帳。
- 保留未來接話需要的狀態。
- 只整理這一段對話造成的新增變化。
- 不要替任何人新增原文沒有的行動或想法。
""".strip(),
    "state": """
請根據「既有目前狀態」與「新分段摘要」，更新成一份最新的目前狀態。

輸出格式固定如下：
【目前場景】
【目前事件位置】
【AI角色目前狀態】
【使用者目前狀態】
【雙方關係狀態】
【必須延續的伏筆】
【下一步應接續】

整理要求：
- 只保留最新狀態，不要保留過期狀態。
- 如果新摘要推翻舊狀態，以新摘要為準。
- 不要寫成聊天回覆。
""".strip(),
    "archive": """
請把多段舊長期摘要合併成更高層封存摘要。

輸出格式固定如下：
【長期背景】
【主要事件脈絡】
【穩定角色關係】
【重要轉折】
【仍可能影響未來的伏筆】

整理要求：
- 壓縮舊資訊，避免冗長。
- 只保留未來可能用到的資訊。
- 不要保留已經沒有影響的細節。
""".strip(),
}


# =========================
# 摘要 / 記憶處理
# =========================
def summarize_memory(gemini_key, source_text=None, summary_type="segment", chat_text=None):

    if source_text is None:
        source_text = chat_text or ""

    source_text = str(source_text or "").strip()

    if not source_text:
        return ""

    instruction = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["segment"])

    prompt = f"""
{MEMORY_PROCESSING_PREFIX}

===記憶整理任務===
{instruction}

===待整理資料===
{source_text}
""".strip()

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
        return text.strip()

    block_reason = get_gemini_block_reason(response)

    if block_reason:
        print("GEMINI summary blocked:", block_reason)
        return MEMORY_SUMMARY_BLOCKED

    return ""
