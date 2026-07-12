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


# 文生圖固定人物身份只負責角色一致性，不把人物推成棚拍美女肖像。
TEXT_IDENTITY_PROFILES: Dict[str, List[str]] = {
    "female": [
        "one adult East Asian woman in her twenties",
        "realistic everyday appearance rather than an idealized beauty model",
        "soft oval face with slight natural asymmetry",
        "dark brown almond-shaped eyes with natural double eyelids",
        "small straight nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "slim naturally proportioned body",
        "natural black hair only as the fallback when no newer request changes it",
        "recognizable character identity shown as part of a real scene rather than a face showcase",
    ],
    "male": [
        "one adult East Asian man in his twenties",
        "realistic everyday appearance rather than an idealized fashion model",
        "balanced masculine oval face with slight natural asymmetry",
        "dark brown almond-shaped eyes",
        "straight natural nose and naturally shaped lips",
        "realistic light skin with visible natural texture and subtle imperfections",
        "lean naturally proportioned body",
        "natural short black hair only as the fallback when no newer request changes it",
        "recognizable character identity shown as part of a real scene rather than a face showcase",
    ],
}


PHOTO_REALISM_RULE = """
Create a genuine real-camera photograph. The default visual language is candid lifestyle photography, documentary photography, editorial location photography, travel photography, or an unstaged everyday snapshot. The image must look captured in a real place by a physical camera, not designed as AI beauty artwork.

Use believable ambient light, realistic exposure, natural dynamic range, ordinary lens perspective, physically plausible shadows, real fabric folds, natural hair strands, visible skin texture, pores, tiny imperfections, slight facial asymmetry, and lived-in environmental details. Avoid glamour retouching, commercial beauty lighting, plastic skin, synthetic perfection, fantasy rendering, illustration, anime, CGI, 3D, game-art styling, and overprocessed HDR.

Treat the newest explicit request as the highest-priority visual instruction. Ignore older details that conflict with it. Do not add unrelated people, props, redesigns, captions, subtitles, watermarks, logos, or invented writing.
""".strip()


NON_PORTRAIT_COMPOSITION_RULE = """
PORTRAIT_POLICY: BLOCK
This is not a portrait session. Do not default to a face-centered composition. Use an environmental medium-wide, three-quarter-body, knee-up, or full-body photograph. Keep enough camera distance to show the requested location, clothing, posture, action, hands, interacting objects, and surrounding environment. The person should occupy only part of the frame and the location must remain visually meaningful.

Prefer candid activity, natural body language, off-center composition, ordinary eye-level camera placement, and 35mm-to-50mm environmental perspective. Do not automatically make the subject stare into the camera. Do not crop at the shoulders or chest. Do not let the face dominate the image. Do not replace the requested scene with a blurred empty background.
""".strip()


PORTRAIT_ALLOWED_COMPOSITION_RULE = """
PORTRAIT_POLICY: ALLOW_EXPLICIT
The newest request explicitly requires portrait-oriented framing. Follow the requested portrait, close-up, headshot, profile image, selfie, or studio composition precisely, while keeping it a believable natural camera photograph with realistic skin and restrained retouching.
""".strip()


IMAGE_TO_IMAGE_GLOBAL_RULE = """
Use the supplied source image as the identity and visual reference, then perform a real photographic edit. The newest explicit request is the required result and must be completed clearly. Do not return the source unchanged, do not merely resize it, and do not hide behind tiny texture changes when a visible wardrobe, pose, action, object, framing, or scene change was requested.

Preserve the same recognizable person and all unrequested visual elements as closely as possible. Larger requested changes may alter pose, body position, hands, camera distance, crop, viewpoint, background, furniture, objects, lighting, and scene composition when necessary. When the newest request explicitly asks to keep the background unchanged, keep the original room, furniture, layout, and scene structure unchanged as much as possible. When the newest request explicitly asks to change the pose or body position, actually change it decisively instead of returning a near-identical pose. Do not introduce an unrequested close-up, beauty crop, headshot, or face-dominant portrait.

The finished edit must retain a genuine real-camera appearance with natural skin texture, realistic ambient light, believable perspective, and no CGI, illustration, anime, plastic skin, or beauty-advertisement finish.
""".strip()


MASK_TO_IMAGE_GLOBAL_RULE = """
Use the supplied source image together with its edit mask. White or light mask pixels are the only regions that may be regenerated. Black mask pixels are protected and must remain visually unchanged as much as the inpainting pipeline allows.

Complete the newest explicit request clearly inside the masked region. Use nearby unmasked pixels for identity, lighting, perspective, texture, anatomy, and scene continuity. If the request is only a color change, keep the original garment design, structure, material, and shape unless the request explicitly asks to change them. Do not redesign the whole image, move the camera, zoom into the face, or convert the source into a portrait. Blend the edited area naturally across the soft mask boundary.

The result must look like a local edit to a real photograph, with matching camera noise, skin texture, lighting, color, depth, and lens perspective. Do not introduce CGI, illustration, anime, plastic skin, or synthetic beauty retouching.
""".strip()


TEXT_NEGATIVE_PROMPT_STRICT = (
    "portrait, close-up portrait, face-only portrait, headshot, beauty headshot, bust shot, "
    "medium close-up, shoulder-up crop, chest-up portrait, face filling frame, centered face, "
    "profile picture, passport photo, ID photo, studio portrait, glamour portrait, beauty portrait, "
    "fashion beauty campaign, commercial beauty lighting, automatic looking at camera, "
    "extreme shallow depth of field, empty bokeh background, blurred unrecognizable environment, "
    "AI generated look, CGI, 3d render, illustration, anime, doll-like face, plastic skin, "
    "beauty filter, excessive retouching, over-smoothed skin, perfect synthetic skin, unrealistic eyes, "
    "fake studio glow, text, subtitles, speech bubbles, watermark, logo, duplicate person, extra limbs, "
    "extra fingers, malformed hands, distorted face, stretched body, compressed body, blurry, low resolution"
)


TEXT_NEGATIVE_PROMPT_PORTRAIT_ALLOWED = (
    "AI generated look, CGI, 3d render, illustration, anime, doll-like face, plastic skin, "
    "beauty filter, excessive retouching, over-smoothed skin, perfect synthetic skin, unrealistic eyes, "
    "fake studio glow, text, subtitles, speech bubbles, watermark, logo, duplicate person, extra limbs, "
    "extra fingers, malformed hands, distorted face, stretched body, compressed body, blurry, low resolution"
)


IMAGE_NEGATIVE_PROMPT = (
    "unchanged source image, resize-only result, no requested edit, weak edit, different person, "
    "face replacement, identity drift, unrelated redesign, unrequested changes, unrequested close-up, "
    "unrequested portrait crop, headshot conversion, beautification, plastic skin, beauty filter, "
    "CGI, 3d render, illustration, anime, altered unrequested background, garbled existing signage, "
    "changed existing text, duplicate person, extra limbs, extra fingers, malformed hands, distorted face, blurry"
)


MASK_NEGATIVE_PROMPT = (
    "changes outside mask, altered protected region, full image redraw, different person, identity drift, "
    "moved camera, changed composition, portrait conversion, unrequested face zoom, changed unmasked background, "
    "hard mask seam, visible cutout edge, mismatched lighting, mismatched color, CGI, illustration, anime, "
    "plastic skin, blurry boundary, duplicate person, extra limbs, extra fingers, malformed hands, distorted face"
)


PORTRAIT_POSITIVE_PATTERNS = [
    r"肖像照", r"肖像攝影", r"人像照", r"人像攝影", r"臉部特寫", r"面部特寫",
    r"頭肩照", r"大頭照", r"證件照", r"個人頭像", r"頭像照", r"胸像", r"半身肖像",
    r"自拍照", r"自拍近照", r"近拍.{0,4}(臉|面部)", r"(臉|面部).{0,4}近拍",
    r"\bportrait\b", r"\bheadshot\b", r"face[- ]?close[- ]?up", r"close[- ]?up portrait",
    r"\bbust portrait\b", r"\bpassport photo\b", r"\bid photo\b", r"\bprofile picture\b",
    r"\bstudio portrait\b", r"\bbeauty portrait\b", r"\bselfie\b",
]


NON_PORTRAIT_POSITIVE_PATTERNS = [
    r"不要.{0,8}(肖像|人像|特寫|大頭照|頭像|證件照)",
    r"避免.{0,8}(肖像|人像|特寫|大頭照|頭像|證件照)",
    r"禁止.{0,8}(肖像|人像|特寫|大頭照|頭像|證件照)",
    r"不是.{0,8}(肖像|人像|特寫|大頭照|頭像|證件照)",
    r"(全身|四分之三身|三分之二身|膝上|中遠景|遠景|廣角|全景|街拍|生活照|場景照|環境照)",
    r"\bfull[- ]?body\b", r"\bthree[- ]?quarter body\b", r"\bknee[- ]?up\b",
    r"\bmedium[- ]?wide\b", r"\bwide shot\b", r"\benvironmental shot\b", r"\bstreet photography\b",
    r"\bnot a portrait\b", r"\bno portrait\b", r"\bavoid portrait\b",
]


def _clean(value, max_len=5000):
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _portrait_requested(sections: Dict[str, str]) -> bool:
    """
    依優先順序判斷使用者是否真的需要肖像。

    先看最高優先需求；若其中明確要求全身、街拍或避免肖像，就不讓舊對話裡的
    「肖像」把構圖重新拉回臉部特寫。
    """
    for key in ("priority", "secondary", "context"):
        text = _clean(sections.get(key), 5000)
        if not text:
            continue
        if _matches_any(text, NON_PORTRAIT_POSITIVE_PATTERNS):
            return False
        if _matches_any(text, PORTRAIT_POSITIVE_PATTERNS):
            return True
    return False


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
    prompt_mode = _clean(prompt_mode, 30)

    if prompt_mode == "custom":
        custom = _clean(custom_prompt)
        if not custom:
            raise ValueError("完全自訂提示詞不可空白")
        return {"priority": custom, "secondary": "", "context": ""}

    source = _clean(source_text)
    if not source:
        raise ValueError("找不到可用的本輪訊息")

    supplement = _clean(supplement_prompt)
    tag_prompt = _fixed_tag_prompt(fixed_tag, gender)

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

    return {"priority": priority, "secondary": secondary, "context": source}


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

    if generation_mode not in {"text", "image", "mask"}:
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
        portrait_requested = _portrait_requested(sections)
        parts.append("MODE: REAL-CAMERA PHOTOGRAPHIC TEXT-TO-IMAGE")
        parts.append(PHOTO_REALISM_RULE)
        parts.append(PORTRAIT_ALLOWED_COMPOSITION_RULE if portrait_requested else NON_PORTRAIT_COMPOSITION_RULE)
        parts.append("CHARACTER IDENTITY: " + ", ".join(TEXT_IDENTITY_PROFILES[gender]))
        negative = (
            TEXT_NEGATIVE_PROMPT_PORTRAIT_ALLOWED
            if portrait_requested
            else TEXT_NEGATIVE_PROMPT_STRICT
        )
    elif generation_mode == "image":
        parts.append("MODE: REAL-PHOTO SOURCE-IMAGE EDIT")
        parts.append(IMAGE_TO_IMAGE_GLOBAL_RULE)
        negative = IMAGE_NEGATIVE_PROMPT
    else:
        parts.append("MODE: REAL-PHOTO MASKED LOCAL INPAINT EDIT")
        parts.append(MASK_TO_IMAGE_GLOBAL_RULE)
        negative = MASK_NEGATIVE_PROMPT

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
        if portrait_requested:
            parts.append(
                "COMPOSITION CHECK: portrait framing is allowed only because the newest request explicitly asks for it. "
                "Keep the result photographic, natural, and unretouched rather than synthetic beauty artwork."
            )
        else:
            parts.append(
                "COMPOSITION CHECK: reject any headshot, shoulder-up crop, chest-up beauty photo, or face-dominant result. "
                "The final image must visibly include the requested scene, clothing, action, hands, objects, and environment."
            )
    elif generation_mode == "image":
        parts.append(
            "EDIT COMPLETION CHECK: the requested edit must be unmistakably visible. Returning the source unchanged, "
            "only resized, or unexpectedly converted into a portrait is a failed result."
        )
    else:
        parts.append(
            "MASK COMPLETION CHECK: make the requested change clearly visible only inside the white mask, preserve black "
            "protected regions, and keep the same photographic composition."
        )

    if sections["priority"]:
        parts.append("MANDATORY FINAL VISUAL RESULT: " + sections["priority"])

    return "\n\n".join(parts) + " ### " + negative
