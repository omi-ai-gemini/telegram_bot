import re
from typing import Dict, List


FIXED_TAGS: Dict[str, str] = {
    "浴衣": "wearing a traditional Japanese yukata with a natural obi and realistic fabric folds",
    "睡衣": "wearing simple realistic home sleepwear with natural fabric folds",
    "禮服": "wearing formal evening clothing with realistic tailoring and fabric texture",
}


# 文生圖只固定人物身份基礎與攝影風格。
# 髮型、服裝、動作、物品、場景等都不是程式逐項判斷，
# 而是交給同一套「最新明確需求優先」規則處理。
TEXT_IDENTITY_PROFILES: Dict[str, List[str]] = {
    "female": [
        "one naturally attractive adult East Asian woman in her twenties",
        "soft oval face with realistic slight facial asymmetry",
        "dark brown almond-shaped eyes with natural double eyelids",
        "small straight nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "slim naturally proportioned body",
        "long natural black hair with light bangs as the default only when no newer request changes it",
        "maintain a consistent recognizable facial identity across images",
    ],
    "male": [
        "one naturally attractive adult East Asian man in his twenties",
        "balanced masculine oval face with realistic slight facial asymmetry",
        "dark brown almond-shaped eyes",
        "straight natural nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "lean naturally proportioned body",
        "short natural black hair as the default only when no newer request changes it",
        "maintain a consistent recognizable facial identity across images",
    ],
}


TEXT_TO_IMAGE_GLOBAL_RULE = """
Create a real camera lifestyle photograph rather than AI artwork, CGI, illustration, beauty-filter portrait, or studio-perfect commercial rendering. Use natural camera exposure, believable dynamic range, realistic skin texture, subtle pores, slight facial asymmetry, natural hair strands, ordinary environmental details, and physically believable light and shadow. Keep the person attractive but human and naturally photographed. Choose a framing that clearly shows the requested clothing, action, object, and scene instead of automatically using a close-up face portrait. Treat the newest explicit request as the highest priority. When any earlier context conflicts with the newest request, follow only the newest request. Do not add unrelated redesigns.
""".strip()


IMAGE_TO_IMAGE_GLOBAL_RULE = """
Use the supplied source image as the visual ground truth. Preserve the same person, recognizable facial identity, body proportions, photographic style, camera angle, crop, pose, lighting, background, objects, signs, and every other visible element that the newest request does not explicitly ask to change. Change only what the newest explicit request asks to change, and keep all unrelated parts as close to the source image as possible. Do not beautify, redesign, restyle, or replace the person without an explicit request. Existing readable signs or text belong to the source image and should remain visually unchanged unless the newest request explicitly asks to edit them. When the newest request conflicts with earlier context or the source image, the newest request wins only for the mentioned part.
""".strip()


TEXT_NEGATIVE_PROMPT = (
    "AI generated look, CGI, 3d render, illustration, anime, doll-like face, plastic skin, "
    "beauty filter, excessive retouching, over-smoothed skin, perfect synthetic skin, "
    "unrealistic eyes, fake studio glow, text, subtitles, speech bubbles, watermark, logo, "
    "duplicate person, extra limbs, extra fingers, malformed hands, distorted face, "
    "stretched body, compressed body, unnatural anatomy, blurry, low resolution"
)

IMAGE_NEGATIVE_PROMPT = (
    "different person, face replacement, identity drift, unrelated redesign, unrequested changes, "
    "beautification, plastic skin, beauty filter, altered unrequested background, "
    "garbled existing signage, changed existing text, duplicate person, extra limbs, "
    "extra fingers, malformed hands, distorted face, stretched body, compressed body, blurry"
)


def _clean(value, max_len=5000):
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _fixed_tag_prompt(tag: str, gender: str) -> str:
    tag = _clean(tag, 50)
    if not tag:
        return ""
    if tag not in FIXED_TAGS:
        raise ValueError("固定標籤不存在")
    if tag == "禮服" and gender == "male":
        return "wearing a fitted formal evening suit with realistic tailoring and fabric texture"
    if tag == "禮服" and gender == "female":
        return "wearing a formal evening gown with realistic tailoring and fabric texture"
    if tag == "禮服":
        return "wearing formal evening clothing with realistic tailoring and fabric texture"
    return FIXED_TAGS[tag]


def _request_sections(
    source_text: str,
    prompt_mode: str,
    gender: str,
    fixed_tag: str,
    supplement_prompt: str,
    custom_prompt: str,
) -> Dict[str, str]:
    """建立通用優先級區塊，不逐項拆髮型、服裝、場景或物品。"""
    prompt_mode = _clean(prompt_mode, 30)

    if prompt_mode == "custom":
        custom = _clean(custom_prompt)
        if not custom:
            raise ValueError("完全自訂提示詞不可空白")
        return {
            "priority": custom,
            "secondary": "",
            "context": "",
        }

    source = _clean(source_text)
    if not source:
        raise ValueError("找不到可用的本輪訊息")

    supplement = _clean(supplement_prompt)
    tag_prompt = _fixed_tag_prompt(fixed_tag, gender)

    # 優先順序：補充提示詞 > 固定標籤 > 本輪對話。
    # 不解析需求屬於髮型、衣服或場景，所有修改共用同一套概念。
    if supplement:
        priority = supplement
        secondary = tag_prompt
    elif tag_prompt:
        priority = tag_prompt
        secondary = ""
    else:
        priority = source
        source = ""
        secondary = ""

    return {
        "priority": priority,
        "secondary": secondary,
        "context": source,
    }


def build_image_prompt(
    source_text: str,
    prompt_mode: str,
    generation_mode: str,
    gender: str = "",
    fixed_tag: str = "",
    supplement_prompt: str = "",
    custom_prompt: str = "",
) -> str:
    generation_mode = _clean(generation_mode, 30)
    gender = _clean(gender, 20)

    if generation_mode not in {"text", "image"}:
        raise ValueError("生圖模式錯誤")
    if generation_mode == "text" and gender not in TEXT_IDENTITY_PROFILES:
        raise ValueError("文生圖必須選擇人物性別")

    sections = _request_sections(
        source_text=source_text,
        prompt_mode=prompt_mode,
        gender=gender,
        fixed_tag=fixed_tag,
        supplement_prompt=supplement_prompt,
        custom_prompt=custom_prompt,
    )

    parts: List[str] = []

    if generation_mode == "text":
        parts.append("MODE: REAL-CAMERA TEXT-TO-IMAGE")
        parts.append(TEXT_TO_IMAGE_GLOBAL_RULE)
        parts.append("CHARACTER IDENTITY: " + ", ".join(TEXT_IDENTITY_PROFILES[gender]))
        negative = TEXT_NEGATIVE_PROMPT
    else:
        parts.append("MODE: SOURCE-PRESERVING IMAGE-TO-IMAGE EDIT")
        parts.append(IMAGE_TO_IMAGE_GLOBAL_RULE)
        negative = IMAGE_NEGATIVE_PROMPT

    if sections["priority"]:
        parts.append("HIGHEST PRIORITY NEWEST REQUEST: " + sections["priority"])
    if sections["secondary"]:
        parts.append("SECONDARY REQUEST, ONLY WHEN IT DOES NOT CONFLICT: " + sections["secondary"])
    if sections["context"]:
        parts.append(
            "SOURCE CONVERSATION CONTEXT, USE ONLY VISUALLY DEPICTABLE DETAILS THAT DO NOT CONFLICT: "
            + sections["context"]
        )

    parts.append(
        "FINAL PRIORITY CHECK: apply the HIGHEST PRIORITY NEWEST REQUEST clearly and visibly; "
        "ignore every conflicting earlier detail. Do not render dialogue, captions, or new written text."
    )

    # 把最高優先需求再次放在結尾，降低長對話吃掉補充提示詞的情況。
    if sections["priority"]:
        parts.append("REQUIRED VISIBLE RESULT: " + sections["priority"])

    return "\n\n".join(parts) + " ### " + negative
