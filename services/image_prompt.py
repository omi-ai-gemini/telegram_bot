import re
from typing import Dict, List


FIXED_TAGS: Dict[str, str] = {
    "浴衣": (
        "clearly wearing a complete traditional Japanese yukata, with the robe, sleeves, "
        "obi sash, and realistic fabric folds visibly shown in the frame"
    ),
    "睡衣": (
        "clearly wearing comfortable home sleepwear, with the pajama outfit and soft relaxed "
        "fabric visibly shown in the frame"
    ),
    "禮服": (
        "clearly wearing formal evening clothing suitable for a banquet or formal event, "
        "with the complete outfit visibly shown in the frame"
    ),
}


# 文生圖只固定人物身份基礎，不逐項解析髮型、服裝、動作、物品或場景。
# 所有更新都交給共用的「最新明確要求優先」規則。
TEXT_IDENTITY_PROFILES: Dict[str, List[str]] = {
    "female": [
        "one adult East Asian woman in her twenties",
        "naturally attractive but realistic everyday appearance",
        "soft oval face with slight natural asymmetry",
        "dark brown almond-shaped eyes with natural double eyelids",
        "small straight nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "slim naturally proportioned body",
        "natural black hair as the default only when no newer request changes it",
        "keep a recognizable character identity without turning the image into a face portrait",
    ],
    "male": [
        "one adult East Asian man in his twenties",
        "naturally attractive but realistic everyday appearance",
        "balanced masculine oval face with slight natural asymmetry",
        "dark brown almond-shaped eyes",
        "straight natural nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "lean naturally proportioned body",
        "natural short black hair as the default only when no newer request changes it",
        "keep a recognizable character identity without turning the image into a face portrait",
    ],
}


TEXT_TO_IMAGE_GLOBAL_RULE = """
Create a candid environmental lifestyle photograph taken with a real camera. The image must tell the requested scene instead of defaulting to a posed beauty portrait. Unless the newest request explicitly asks for a close-up, use a medium-wide, three-quarter-body, or full-body composition. Keep enough camera distance to show the requested clothing, posture, action, hand interaction, object, and surrounding environment clearly. When a location or scene is mentioned, the environment must occupy a meaningful part of the frame and remain recognizable rather than becoming a generic blurred backdrop.

Avoid centered head-and-shoulders portraits, face-only framing, studio headshots, glamour photography, beauty-advertisement poses, empty blurred backgrounds, and automatic looking-at-camera poses. Use natural camera exposure, believable dynamic range, realistic skin texture, subtle pores, slight facial asymmetry, natural hair strands, ordinary environmental details, and physically believable light and shadow. Keep the person attractive but human and naturally photographed, not CGI, illustration, or an over-retouched AI beauty image.

Treat the newest explicit request as the highest-priority visual instruction. When earlier context conflicts with the newest request, ignore the conflicting earlier detail. Do not add unrelated redesigns. Do not render dialogue, captions, subtitles, watermarks, or newly invented written text.
""".strip()


IMAGE_TO_IMAGE_GLOBAL_RULE = """
Use the supplied source image as the identity and visual reference, then perform a real image edit. The newest explicit request is the target result and must be completed clearly. Do not return the source image unchanged, do not merely resize it, and do not hide behind tiny texture changes when the request asks for different clothing, pose, action, framing, visible body area, object, or scene.

Preserve the same recognizable person, facial identity, and overall character as closely as possible, together with any visual parts that are not asked to change. However, if the newest request implies a larger edit, you are allowed and expected to change pose, body position, hand position, camera distance, crop, framing, viewpoint, background, room, bed, furniture, objects, lighting, and scene composition as needed to satisfy the request. Do not preserve the original pose, crop, or background when they block the requested result.

Apply the requested clothing change as a real wardrobe replacement. Apply the requested scene change as a real scene change. Apply the requested pose or action as a real pose or action change. Preserve existing signs or readable text only when they are outside the requested edit and do not conflict with the requested result.

Do not beautify, redesign, restyle, or replace the person without an explicit request. Keep a realistic camera-photo look with natural skin texture and believable lighting.
""".strip()


TEXT_NEGATIVE_PROMPT = (
    "close-up portrait, face-only portrait, headshot, studio portrait, glamour portrait, "
    "beauty advertisement, centered face, blurred empty background, automatic looking at camera, "
    "AI generated look, CGI, 3d render, illustration, anime, doll-like face, plastic skin, "
    "beauty filter, excessive retouching, over-smoothed skin, perfect synthetic skin, "
    "unrealistic eyes, fake studio glow, text, subtitles, speech bubbles, watermark, logo, "
    "duplicate person, extra limbs, extra fingers, malformed hands, distorted face, "
    "stretched body, compressed body, unnatural anatomy, blurry, low resolution"
)

IMAGE_NEGATIVE_PROMPT = (
    "unchanged source image, resize-only result, no requested edit, weak edit, "
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
        return (
            "clearly wearing a complete fitted formal evening suit, including a visible suit jacket "
            "and matching formal trousers, suitable for a banquet or formal evening event"
        )
    if tag == "禮服" and gender == "female":
        return (
            "clearly wearing a complete formal evening gown, with the long elegant gown visibly shown, "
            "suitable for a banquet or formal evening event"
        )
    return FIXED_TAGS[tag]


def _request_sections(
    source_text: str,
    prompt_mode: str,
    gender: str,
    fixed_tag: str,
    supplement_prompt: str,
    custom_prompt: str,
) -> Dict[str, str]:
    """建立共用優先級，不按髮型、衣服、場景等類別逐項拆規則。"""
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
        parts.append("MODE: ENVIRONMENTAL REAL-CAMERA TEXT-TO-IMAGE")
        parts.append(TEXT_TO_IMAGE_GLOBAL_RULE)
        parts.append("CHARACTER IDENTITY: " + ", ".join(TEXT_IDENTITY_PROFILES[gender]))
        negative = TEXT_NEGATIVE_PROMPT
    else:
        parts.append("MODE: REQUIRED SOURCE-IMAGE EDIT")
        parts.append(IMAGE_TO_IMAGE_GLOBAL_RULE)
        negative = IMAGE_NEGATIVE_PROMPT

    if sections["priority"]:
        parts.append("HIGHEST PRIORITY REQUIRED RESULT: " + sections["priority"])
    if sections["secondary"]:
        parts.append("SECONDARY REQUEST, ONLY WHEN IT DOES NOT CONFLICT: " + sections["secondary"])
    if sections["context"]:
        parts.append(
            "SOURCE CONVERSATION CONTEXT, USE ONLY VISUALLY DEPICTABLE DETAILS THAT DO NOT CONFLICT: "
            + sections["context"]
        )

    if generation_mode == "text":
        parts.append(
            "COMPOSITION CHECK: do not use a close-up or headshot unless explicitly requested. "
            "Show the character together with the requested clothing, action, object, and environment."
        )
    else:
        parts.append(
            "EDIT COMPLETION CHECK: the requested edit must be unmistakably visible. "
            "Returning the source unchanged or only resized is a failed result."
        )
        parts.append(
            "MAJOR EDIT POLICY: if the newest request asks for a different pose, different clothing, "
            "different visible body area, wider framing, different room, different bed, or different scene, "
            "you must change those parts decisively even when that requires changing the original pose, crop, "
            "camera framing, or background. Preserve identity, but do not let preservation block the requested edit."
        )

    # 最高優先需求在結尾再次強調，避免長對話吃掉補充或完全自訂提示詞。
    if sections["priority"]:
        parts.append("MANDATORY FINAL VISUAL RESULT: " + sections["priority"])

    return "\n\n".join(parts) + " ### " + negative
