import re
from typing import Dict, Iterable, List, Set


FIXED_TAGS: Dict[str, str] = {
    "浴衣": "traditional Japanese yukata",
    "睡衣": "realistic home sleepwear",
    "禮服": "formal evening wear",
}


# 只固定人物身份，不把髮型、服裝、姿勢或場景鎖死。
# 系統預設生圖使用這些描述；玩家指定聊天室圖片或上傳圖片時不套用。
IDENTITY_PROFILES: Dict[str, List[str]] = {
    "female": [
        "one attractive adult East Asian woman in her early twenties",
        "balanced oval face with refined symmetrical facial proportions",
        "clear dark almond-shaped eyes with natural double eyelids",
        "small straight nose",
        "natural softly shaped lips",
        "smooth fair skin with realistic skin texture",
        "slim and naturally proportioned body",
        "consistent recognizable facial identity across images",
    ],
    "male": [
        "one attractive adult East Asian man in his early twenties",
        "balanced masculine oval face with refined symmetrical facial proportions",
        "clear dark almond-shaped eyes",
        "straight natural nose",
        "natural well-shaped lips",
        "clean fair skin with realistic skin texture",
        "lean and naturally proportioned body",
        "consistent recognizable facial identity across images",
    ],
}


DEFAULT_APPEARANCE: Dict[str, Dict[str, str]] = {
    "female": {
        "hair_color": "natural black hair",
        "hair_length": "long hair",
        "hair_style": "straight hair with soft natural bangs",
    },
    "male": {
        "hair_color": "natural black hair",
        "hair_length": "short hair",
        "hair_style": "neat naturally textured hairstyle",
    },
}


# 用來判斷高優先級需求是否明確指定某個外觀欄位。
OVERRIDE_PATTERNS: Dict[str, List[str]] = {
    "hair_color": [
        r"黑髮|黑色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"金髮|金色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"棕髮|棕色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"紅髮|紅色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"白髮|銀髮|白色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)|銀色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"藍髮|藍色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"粉髮|粉色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"紫髮|紫色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"綠髮|綠色(?:的)?[^，。,.;；\n]{0,6}(?:髮|頭髮)",
        r"black hair|blond(?:e)? hair|brown hair|red hair|white hair|silver hair|blue hair|pink hair|purple hair|green hair",
    ],
    "hair_length": [
        r"短(?:直|捲|波浪)?髮|耳下短(?:直|捲|波浪)?髮|及肩短(?:直|捲|波浪)?髮|中長(?:直|捲|波浪)?髮|及肩(?:直|捲|波浪)?髮|長(?:直|捲|波浪)?髮|及腰長(?:直|捲|波浪)?髮|光頭|剃光",
        r"short(?:\s+[a-z-]+){0,2}\s+hair|bob cut|pixie cut|medium(?:-length)?(?:\s+[a-z-]+){0,2}\s+hair|shoulder-length(?:\s+[a-z-]+){0,2}\s+hair|long(?:\s+[a-z-]+){0,2}\s+hair|waist-length(?:\s+[a-z-]+){0,2}\s+hair|bald|shaved head",
    ],
    "hair_style": [
        r"直髮|捲髮|波浪髮|馬尾|雙馬尾|包頭|髮髻|髻|編髮|辮子|齊瀏海|側分瀏海|瀏海|油頭",
        r"straight hair|curly hair|wavy hair|ponytail|twin tails|pigtails|bun hairstyle|hair bun|braid(?:ed)? hair|bangs|fringe|undercut|slicked-back hair",
    ],
}


NEGATIVE_PROMPT = (
    "text, subtitles, speech bubbles, watermark, logo, duplicate person, extra limbs, "
    "extra fingers, malformed hands, distorted face, stretched body, compressed body, "
    "unnatural anatomy, plastic skin, low resolution, blurry"
)


def _clean(value, max_len=5000):
    text = str(value or "").replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _override_fields(text: str) -> Set[str]:
    text = _clean(text)
    result: Set[str] = set()
    for field, patterns in OVERRIDE_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            result.add(field)
    return result


def _clean_punctuation(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([，。,.;；])\s*", r"\1", text)
    text = re.sub(r"([，,;；]){2,}", r"\1", text)
    text = re.sub(r"^[，。,.;；\s]+|[，,;；\s]+$", "", text)
    return text.strip()


def _remove_lower_priority_hair_traits(text: str, fields: Iterable[str]) -> str:
    """只從較低優先級文字移除衝突的髮型片段，不改場景、動作或表情。"""
    result = _clean(text)
    field_set = set(fields)
    if not result or not field_set:
        return result

    if {"hair_color", "hair_length", "hair_style"}.issubset(field_set):
        # 高優先級完整指定新髮型時，直接移除較低優先級的整段髮型描述。
        result = re.sub(
            r"(?:黑色|黑|金色|金|棕色|棕|紅色|紅|白色|白|銀色|銀|藍色|藍|粉色|粉|紫色|紫|綠色|綠)?"
            r"(?:及腰|及肩|耳下|中長|長|短)?"
            r"(?:直|捲|波浪)?(?:頭髮|髮)",
            "",
            result,
        )
        result = re.sub(
            r"\b(?:black|blond(?:e)?|brown|red|white|silver|blue|pink|purple|green)?\s*"
            r"(?:waist-length|shoulder-length|medium-length|long|short)?\s*"
            r"(?:straight|curly|wavy)?\s*hair\b",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"(?:她|他|人物)?有(?=[，。,.;；])", "", result)

    if "hair_color" in field_set:
        # 只在髮型語境內移除顏色，避免刪掉衣服或場景的顏色。
        color_words = (
            r"黑色|黑|金色|金|棕色|棕|紅色|紅|白色|白|銀色|銀|"
            r"藍色|藍|粉色|粉|紫色|紫|綠色|綠"
        )
        result = re.sub(
            rf"(?:{color_words})(?=[^，。,.;；\n]{{0,7}}(?:髮|頭髮))",
            "",
            result,
        )
        result = re.sub(
            r"\b(?:black|blond(?:e)?|brown|red|white|silver|blue|pink|purple|green)\s+(?=(?:[a-z-]+\s+){0,2}hair\b)",
            "",
            result,
            flags=re.IGNORECASE,
        )

    if "hair_length" in field_set:
        result = re.sub(
            r"(?:耳下|及肩|及腰|中長|長|短)(?=[^，。,.;；\n]{0,4}(?:髮|頭髮))",
            "",
            result,
        )
        result = re.sub(
            r"\b(?:short|long|medium-length|shoulder-length|waist-length)\s+(?=(?:[a-z-]+\s+){0,2}hair\b)",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\b(?:bob cut|pixie cut|bald|shaved head)\b", "", result, flags=re.IGNORECASE)
        result = re.sub(r"光頭|剃光", "", result)

    if "hair_style" in field_set:
        result = re.sub(
            r"(?:直|捲|波浪)(?=[^，。,.;；\n]{0,4}(?:髮|頭髮))",
            "",
            result,
        )
        result = re.sub(
            r"馬尾|雙馬尾|包頭|髮髻|編髮|辮子|齊瀏海|側分瀏海|瀏海|油頭",
            "",
            result,
        )
        result = re.sub(
            r"\b(?:straight|curly|wavy)\s+(?=(?:[a-z-]+\s+){0,2}hair\b)|"
            r"\b(?:ponytail|twin tails|pigtails|bun hairstyle|hair bun|braided hair|bangs|fringe|undercut|slicked-back hair)\b",
            "",
            result,
            flags=re.IGNORECASE,
        )

    return _clean_punctuation(result)


def _appearance_prompt(gender: str, request_text: str) -> List[str]:
    defaults = DEFAULT_APPEARANCE[gender]
    overridden = _override_fields(request_text)
    result = []
    for field in ("hair_color", "hair_length", "hair_style"):
        if field not in overridden:
            result.append(defaults[field])
    return result


def _fixed_tag_prompt(tag: str, gender: str) -> str:
    if not tag:
        return ""
    if tag not in FIXED_TAGS:
        raise ValueError("固定標籤不存在")
    if tag == "浴衣":
        return "wearing a fitted traditional Japanese yukata with a natural obi and realistic fabric details"
    if tag == "睡衣":
        return "wearing simple realistic home sleepwear with natural fabric folds"
    if tag == "禮服" and gender == "male":
        return "wearing a fitted formal evening suit with refined realistic fabric details"
    if tag == "禮服":
        return "wearing a fitted formal evening gown with refined realistic fabric details"
    return FIXED_TAGS[tag]


def build_image_prompt(
    source_text: str,
    prompt_mode: str,
    gender: str,
    fixed_tag: str = "",
    supplement_prompt: str = "",
    custom_prompt: str = "",
    use_system_identity: bool = True,
    use_reference_image: bool = False,
) -> str:
    prompt_mode = _clean(prompt_mode, 30)
    gender = _clean(gender, 20)
    if gender not in IDENTITY_PROFILES:
        raise ValueError("性別設定錯誤")

    if prompt_mode == "custom":
        request_text = _clean(custom_prompt)
        if not request_text:
            raise ValueError("完全自訂提示詞不可空白")
    else:
        source = _clean(source_text)
        if not source:
            raise ValueError("找不到可用的本輪訊息")

        supplement = _clean(supplement_prompt)
        # 補充提示詞優先於本輪訊息；明確指定髮色／長度／造型時，
        # 先從本輪訊息移除同欄位的舊描述，避免同時送出互相衝突的髮型。
        source = _remove_lower_priority_hair_traits(source, _override_fields(supplement))
        tag_prompt = _fixed_tag_prompt(_clean(fixed_tag, 50), gender)
        request_text = ". ".join(value for value in [source, tag_prompt, supplement] if value)

    positive_parts: List[str] = [
        "photorealistic high-quality cinematic photography",
    ]

    if use_system_identity:
        positive_parts.extend(IDENTITY_PROFILES[gender])
        positive_parts.extend(_appearance_prompt(gender, request_text))
    elif use_reference_image:
        positive_parts.extend([
            "preserve the same adult person's recognizable facial identity from the reference image",
            "preserve natural facial proportions without copying the original background or clothing unless requested",
        ])

    positive_parts.extend([
        request_text,
        "the latest explicit request has the highest priority over earlier hairstyle, hair color, clothing, pose and scene descriptions",
        "natural human anatomy and proportions",
        "clear facial features, realistic lighting, coherent composition",
        "no written text in the image",
    ])

    # AI Horde 圖片提示詞使用 ### 分隔正向與負向提示詞。
    return ", ".join(part for part in positive_parts if part) + " ### " + NEGATIVE_PROMPT
