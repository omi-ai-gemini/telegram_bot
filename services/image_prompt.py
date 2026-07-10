import re
from typing import Dict


FIXED_TAGS: Dict[str, str] = {
    "浴衣": "人物穿著合身的傳統日式浴衣，布料、腰帶與衣襟細節自然，服裝完整並符合畫面場景。",
    "睡衣": "人物穿著簡潔自然的居家睡衣，布料質感真實，造型像日常生活中的寫實照片。",
    "禮服": "人物穿著正式合身的晚宴禮服，剪裁與布料細節清楚，姿態自然且具有寫實攝影感。",
}

# 這段直接送給 AI Horde 的圖片模型，不會先交給 Gemini。
IMAGE_TASK_PROMPT = """
先整理訊息內容：把以上文字轉成一張圖片可以呈現的明確畫面，只保留人物外觀、服裝、姿勢、動作、表情、場景、光線與構圖。若文字含有對話、括號動作或敘事，請理解其畫面含義後自然呈現，不要把文字、對話框、字幕或浮水印畫進圖片。以參考圖中的人物外貌與主要特徵作為同一人物，保持寫實照片風格、自然人體比例、清楚五官與完整構圖。只生成圖片，不要輸出任何文字說明。
""".strip()


def _clean(value, max_len=5000):
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def build_image_prompt(
    source_text: str,
    prompt_mode: str,
    fixed_tag: str = "",
    supplement_prompt: str = "",
    custom_prompt: str = "",
) -> str:
    prompt_mode = _clean(prompt_mode, 30)
    parts = []

    if prompt_mode == "custom":
        custom = _clean(custom_prompt)
        if not custom:
            raise ValueError("完全自訂提示詞不可空白")
        parts.append(custom)
    else:
        source = _clean(source_text)
        if not source:
            raise ValueError("找不到可用的本輪訊息")
        parts.append(f"本輪內容：{source}")

        tag = _clean(fixed_tag, 50)
        if tag:
            tag_prompt = FIXED_TAGS.get(tag)
            if not tag_prompt:
                raise ValueError("固定標籤不存在")
            parts.append(f"固定需求：{tag_prompt}")

        supplement = _clean(supplement_prompt)
        if supplement:
            parts.append(f"補充需求：{supplement}")

    parts.append(IMAGE_TASK_PROMPT)
    return "\n\n".join(parts)
