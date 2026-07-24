import json
import os
import re
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from services.local_ai_gateway_client import (
    gateway_config_error,
    gateway_enabled,
    gateway_reverse_enabled,
    gateway_post_json,
    gateway_requested,
)
from services.local_ai_tasks import create_local_ai_task, wait_for_local_ai_task_result


_OLLAMA_SESSION = requests.Session()

OLLAMA_BASE_URL = str(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
OLLAMA_DEPUTY_MODEL = str(os.getenv("OLLAMA_DEPUTY_MODEL", "qwen2.5:7b")).strip() or "qwen2.5:7b"
OLLAMA_PROMPT_MODEL = str(os.getenv("OLLAMA_PROMPT_MODEL", OLLAMA_DEPUTY_MODEL)).strip() or OLLAMA_DEPUTY_MODEL
OLLAMA_TIMEOUT_SECONDS = max(30, int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180") or "180"))
OLLAMA_CHAT_NUM_PREDICT = max(64, int(os.getenv("OLLAMA_CHAT_NUM_PREDICT", "512") or "512"))
OLLAMA_PROMPT_NUM_PREDICT = max(128, int(os.getenv("OLLAMA_PROMPT_NUM_PREDICT", "1200") or "1200"))

IMAGE_PROMPT_KEYS = ("main_positive", "main_negative", "face_positive", "face_negative")
IMAGE_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in IMAGE_PROMPT_KEYS},
    "required": list(IMAGE_PROMPT_KEYS),
    "additionalProperties": False,
}


FACE_NEGATIVE = (
    "cross-eyed, asymmetrical eyes, mismatched eyes, deformed eyes, blurry eyes, "
    "malformed pupils, extra pupils, deformed face, bad anatomy, blurry, low quality, "
    "plastic skin, over-smoothed face"
)

FACE_SUFFIX = (
    "natural detailed eyes, symmetrical eyes, detailed dark brown irises, realistic eyelashes, "
    "natural eye reflections, subtle natural makeup, realistic skin texture, clean facial details"
)

FACE_IDENTITY_PREFIX = {
    ("Chinese", "woman"): "young Chinese woman, Han Chinese facial features, natural Chinese facial structure",
    ("Chinese", "man"): "young Chinese man, Han Chinese facial features, natural Chinese facial structure",
    ("Japanese", "woman"): "young Japanese woman, natural Japanese facial features, natural Japanese facial structure",
    ("Japanese", "man"): "young Japanese man, natural Japanese facial features, natural Japanese facial structure",
    ("Korean", "woman"): "young Korean woman, natural Korean facial features, natural Korean facial structure",
    ("Korean", "man"): "young Korean man, natural Korean facial features, natural Korean facial structure",
    ("Taiwanese", "woman"): "young Taiwanese woman, natural Taiwanese facial features, natural Taiwanese facial structure",
    ("Taiwanese", "man"): "young Taiwanese man, natural Taiwanese facial features, natural Taiwanese facial structure",
    ("Western", "woman"): "young Western woman, natural Western facial features, natural Western facial structure",
    ("Western", "man"): "young Western man, natural Western facial features, natural Western facial structure",
    ("EastAsian", "woman"): "young East Asian woman, natural East Asian facial features, natural East Asian facial structure",
    ("EastAsian", "man"): "young East Asian man, natural East Asian facial features, natural East Asian facial structure",
}


IMAGE_PROMPT_SYSTEM = r"""
你是 Telemini 的圖片提示詞整理器。請把使用者需求忠實整理成 SDXL／ComfyUI 使用的四欄英文 JSON，不要輸出其他文字。

欄位：
main_positive：人物、外觀、服裝、動作、表情、鏡位、場景、光線與寫實攝影風格。
main_negative：使用者禁止項目、構圖錯誤、低畫質、肢體與手部錯誤及非寫實風格。
face_positive：只放臉部生成與修復需要的年齡感、五官、妝容、膚質與自然美感。
face_negative：只放眼睛、瞳孔、五官比例、皮膚與臉部變形錯誤。

規則：
1. 使用者明確指定的國籍、族群、性別、年齡、外貌、服裝、動作、表情、構圖、背景與禁止項目全部優先，不可改寫或省略。
2. 不要擅自增加服裝、物品、劇情、國籍或動作。未指定的內容才可補值。
3. 預設採符合大眾審美、自然寫實且不過度整形的美感：協調五官、自然臉型、清晰眼睛、自然眉毛、比例合適的鼻子與嘴唇、自然妝容、真實皮膚紋理。
4. 美感補詞要短：臉型、眼睛、鼻子、嘴唇各最多 1 個描述；妝容最多 1 個；皮膚最多 2 個。不要堆滿固定詞，保留使用者需求權重。
5. 使用者說可愛、甜美、清純時，採柔和年輕感；說成熟、氣質、冷感、優雅時，採成熟精緻感；未指定時採自然耐看型。男性同理，未指定時採自然帥氣型。
6. 除非使用者明確要求特寫、肖像或自拍，預設使用 medium-long shot, three-quarter body shot, visible from head to knees，並避免 close-up、headshot、face filling the frame。
7. 未指定背景時，依人物、動作與氣氛補一個真實且不搶主體的環境；未指定動作才補 natural standing pose；未指定表情才補 relaxed natural expression。
8. 全身要求必須保留 full body shot, entire body visible, feet visible；不要特寫時必須保留 medium-long shot 與 camera positioned farther away。
9. 瀏海翻成 bangs；空氣瀏海翻成 wispy air bangs；鯊魚夾翻成 claw hair clip。腦後鯊魚夾盤髮要表達為 compact rounded claw clip updo，不能變成垂下馬尾或正式包頭。
10. main_positive 與 face_positive 不要大量重複。四欄只使用英文逗號分隔，不寫故事、解釋、Markdown 或標題。

最低品質補詞：
main_negative 可簡短加入 low quality, blurry, bad anatomy, deformed hands, extra fingers, missing fingers, plastic skin, anime, cartoon, illustration。
face_negative 可簡短加入 cross-eyed, asymmetrical eyes, malformed pupils, extra pupils, distorted facial proportions, plastic skin, over-smoothed skin, deformed face, blurry face。

輸出格式：
{
  "main_positive": "...",
  "main_negative": "...",
  "face_positive": "...",
  "face_negative": "..."
}
""".strip()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_visual_terms(value: Any) -> str:
    text = str(value or "")
    replacements = [
        (r"(稀疏|sparse)\s*(空氣|空气|air)?\s*(瀏海|刘海)", "sparse wispy air bangs"),
        (r"(空氣|空气|air)\s*(瀏海|刘海)", "wispy air bangs"),
        (r"(瀏海|刘海)", "bangs"),
        (r"(鯊魚夾|鲨鱼夹)", "claw hair clip"),
        (r"\bshark\s+clip\b", "claw hair clip"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return _clean_text(text)


def _add_terms(text: str, terms) -> str:
    text = _clean_text(text).strip(",")
    low = text.lower()
    additions = [term for term in terms if term.lower() not in low]
    return ", ".join([item for item in [text, *additions] if item])


def _remove_terms(text: str, terms) -> str:
    banned = [term.lower() for term in terms]
    parts = []
    for part in [p.strip() for p in str(text or "").split(",") if p.strip()]:
        if not any(term in part.lower() for term in banned):
            parts.append(part)
    return ", ".join(parts)


def _has_claw_clip_updo_request(text: str) -> bool:
    low = str(text or "").lower()
    has_clip = any(k in low for k in ("鯊魚夾", "鲨鱼夹", "shark clip", "claw clip", "claw hair clip"))
    has_back = any(k in low for k in ("腦後", "脑后", "後腦", "后脑", "back of the head"))
    has_gather = any(k in low for k in ("整理起來", "整理起来", "夾起來", "夹起来", "收起來", "收起来", "盤起", "盘起", "gathered", "updo"))
    has_bun_like = any(k in low for k in ("包包頭", "丸子頭", "丸子头", "bun-like", "bun like"))
    return has_clip and (has_back or has_gather or has_bun_like)


def _apply_visual_translation_locks(source_text: str, fields: Dict[str, str]) -> None:
    for key in ("main_positive", "main_negative", "face_positive", "face_negative"):
        fields[key] = _normalize_visual_terms(fields.get(key))

    normalized_source = _normalize_visual_terms(source_text)
    if _has_claw_clip_updo_request(source_text) or _has_claw_clip_updo_request(normalized_source):
        fields["main_positive"] = _add_terms(_remove_terms(fields.get("main_positive"), [
            "long hair tied back with claw hair clip",
            "hair tied back with claw hair clip",
            "ponytail", "low ponytail", "hair tail", "loose hanging hair", "formal bun", "tight bun"
        ]), [
            "compact rounded claw clip updo at the back of the head",
            "all long hair gathered upward and secured with a claw hair clip",
            "bun-like shape but not a formal bun",
            "no loose hanging hair tail"
        ])
        fields["main_negative"] = _add_terms(fields.get("main_negative"), [
            "loose hanging hair", "loose ponytail", "low ponytail", "long hair tail",
            "hair falling from the clip", "single hair bundle", "formal bun", "tight bun"
        ])


def _portrait_requested(text: str) -> bool:
    source = str(text or "").lower()
    positive_patterns = (
        "肖像", "人像照", "人像攝影", "人像摄影", "特寫", "特写", "大頭照", "大头照",
        "頭像", "头像", "證件照", "证件照", "自拍", "近拍臉", "脸部近拍", "臉部近拍", "胸像",
        "portrait", "headshot", "close-up", "close up", "selfie", "profile picture",
        "passport photo", "id photo", "studio portrait", "beauty portrait",
    )
    negative_patterns = (
        "不要特寫", "不要特写", "不要大頭", "不要大头", "不要肖像", "不要人像",
        "避免特寫", "避免特写", "避免大頭", "避免大头", "不是特寫", "不是特写",
        "全身", "三分之二身", "四分之三身", "膝上", "中遠景", "中远景", "遠景", "远景",
        "街拍", "生活照", "環境照", "場景照", "full body", "three-quarter body",
        "knee-up", "medium-long", "medium wide", "wide shot", "environmental shot",
        "not a portrait", "no portrait", "avoid portrait",
    )
    if any(token in source for token in negative_patterns):
        return False
    return any(token in source for token in positive_patterns)


def _apply_identity_and_composition_locks(source_text: str, fields: Dict[str, str]) -> None:
    source = str(source_text or "").lower()

    identity_rules = [
        (
            ("中國", "中国", "中國人", "中国人", "華人", "华人", "漢人", "汉人", "chinese", "han chinese"),
            ["Chinese", "Han Chinese facial features", "natural Chinese facial structure"],
            [
                "Western", "Caucasian", "European", "white woman", "white man", "white girl", "white boy",
                "American", "Russian", "Ukrainian", "French", "British", "Nordic", "Slavic",
                "Japanese", "Korean", "Taiwanese", "Southeast Asian", "Thai", "Vietnamese", "Filipino",
                "Latina", "Middle Eastern", "Indian", "South Asian", "blue eyes", "green eyes",
                "gray eyes", "grey eyes", "blonde hair", "blond hair", "platinum blonde hair",
                "red hair", "light-colored eyes", "light colored eyes",
            ],
        ),
        (
            ("日本", "日本人", "japanese"),
            ["Japanese", "natural Japanese facial features", "natural Japanese facial structure"],
            ["Western", "Caucasian", "European", "Chinese", "Han Chinese", "Korean", "Taiwanese"],
        ),
        (
            ("韓國", "韩国", "韓國人", "韩国人", "korean"),
            ["Korean", "natural Korean facial features", "natural Korean facial structure"],
            ["Western", "Caucasian", "European", "Chinese", "Han Chinese", "Japanese", "Taiwanese"],
        ),
        (
            ("台灣", "台湾", "台灣人", "台湾人", "taiwan", "taiwanese"),
            ["Taiwanese", "East Asian facial features", "natural Taiwanese facial structure"],
            ["Western", "Caucasian", "European", "Chinese mainland", "Japanese", "Korean"],
        ),
    ]

    for keywords, required, conflicts in identity_rules:
        if any(keyword in source for keyword in keywords):
            fields["main_positive"] = _add_terms(_remove_terms(fields.get("main_positive"), conflicts), required)
            fields["face_positive"] = _add_terms(_remove_terms(fields.get("face_positive"), conflicts), required)
            fields["main_negative"] = _add_terms(fields.get("main_negative"), conflicts)
            break

    if not _portrait_requested(source_text):
        fields["main_positive"] = _add_terms(
            _remove_terms(fields.get("main_positive"), [
                "portrait", "headshot", "close-up", "close up", "bust shot", "shoulder-up",
                "chest-up", "selfie", "profile picture", "studio portrait", "beauty portrait",
                "face-focused", "face dominant", "tight crop",
            ]),
            [
                "medium-long shot", "three-quarter body shot", "visible from head to knees",
                "camera positioned farther away", "more environment visible",
                "balanced subject-to-background composition", "subject not filling the frame",
                "environment clearly readable", "hands visible when reasonable", "not face-focused",
            ],
        )
        fields["main_negative"] = _add_terms(fields.get("main_negative"), [
            "portrait", "close-up", "extreme close-up", "close-up portrait", "face-only shot",
            "face-only portrait", "headshot", "beauty headshot", "portrait crop", "bust shot",
            "medium close-up", "shoulder-up shot", "shoulder-up crop", "chest-up framing",
            "chest-up portrait", "tight framing", "zoomed-in face", "large face in frame",
            "face filling the frame", "centered face", "profile picture", "passport photo",
            "ID photo", "studio portrait", "glamour portrait", "beauty portrait",
        ])


def _test_normalize_visual_terms(text: str) -> str:
    replacements = [
        ("稀疏空氣瀏海", "sparse wispy air bangs"),
        ("稀疏空气刘海", "sparse wispy air bangs"),
        ("sparse air刘海", "sparse wispy air bangs"),
        ("空氣瀏海", "wispy air bangs"),
        ("空气刘海", "wispy air bangs"),
        ("air刘海", "wispy air bangs"),
        ("瀏海", "bangs"),
        ("刘海", "bangs"),
        ("鯊魚夾", "claw hair clip"),
        ("鲨鱼夹", "claw hair clip"),
        ("shark clip", "claw hair clip"),
    ]
    normalized = str(text or "")
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return " ".join(normalized.split())


def _test_apply_visual_translation_locks(user_text: str, fields: Dict[str, str]) -> None:
    for key in IMAGE_PROMPT_KEYS:
        fields[key] = _test_normalize_visual_terms(fields.get(key, ""))

    normalized_user = _test_normalize_visual_terms(user_text)
    if _has_claw_clip_updo_request(user_text) or _has_claw_clip_updo_request(normalized_user):
        fields["main_positive"] = _add_terms(_remove_terms(fields["main_positive"], [
            "long hair tied back with claw hair clip",
            "hair tied back with claw hair clip",
            "ponytail", "low ponytail", "hair tail", "loose hanging hair", "formal bun", "tight bun"
        ]), [
            "compact rounded claw clip updo at the back of the head",
            "all long hair gathered upward and secured with a claw hair clip",
            "bun-like shape but not a formal bun",
            "no loose hanging hair tail"
        ])
        fields["main_negative"] = _add_terms(fields["main_negative"], [
            "loose hanging hair", "loose ponytail", "low ponytail", "long hair tail",
            "hair falling from the clip", "single hair bundle", "formal bun", "tight bun"
        ])


def _test_has_explicit_background(text: str) -> bool:
    keywords = (
        "背景", "場景", "在", "室內", "室外", "街", "路", "巷", "咖啡廳", "咖啡店", "餐廳", "酒吧",
        "辦公室", "公司", "教室", "校園", "公園", "海邊", "沙灘", "森林", "山", "河", "湖", "神社", "寺",
        "房間", "客廳", "臥室", "床上", "浴室", "廚房", "陽台", "夜市", "商場", "地鐵", "車站",
        "street", "cafe", "restaurant", "office", "park", "beach", "forest", "bedroom", "living room", "bathroom", "city"
    )
    return any(k.lower() in str(text or "").lower() for k in keywords)


def _test_infer_background_terms(user_text: str) -> list[str]:
    if any(k in user_text for k in ("海邊", "沙灘", "泳裝", "比基尼", "泳池")):
        return ["natural beach background", "realistic seaside environment", "daylight", "more environment visible"]
    if any(k in user_text for k in ("咖啡", "咖啡廳", "咖啡店", "下午茶", "甜點")):
        return ["cozy cafe background", "realistic indoor environment", "warm natural lighting", "visible environmental context"]
    if any(k in user_text for k in ("辦公", "上班", "公司", "西裝", "襯衫", "商務", "會議")):
        return ["modern office background", "realistic indoor workspace", "clean professional environment", "visible environmental context"]
    if any(k in user_text for k in ("臥室", "睡衣", "床", "房間", "居家", "客廳", "沙發")):
        return ["realistic home interior background", "clean living environment", "natural indoor lighting", "visible room context"]
    if any(k in user_text for k in ("運動", "健身", "跑步", "瑜伽", "球", "gym")):
        return ["realistic sports environment", "natural activity background", "visible environmental context"]
    if any(k in user_text for k in ("雨", "夜", "晚", "夜晚", "霓虹", "街拍", "都市", "城市")):
        return ["realistic urban street background", "visible city environment", "environmental lighting", "more environment visible"]
    if any(k in user_text for k in ("和服", "浴衣", "神社", "寺", "日式")):
        return ["realistic traditional Japanese setting", "visible environmental context", "natural background"]
    if any(k in user_text for k in ("校園", "學生", "教室", "圖書館")):
        return ["realistic campus background", "visible school environment", "natural daylight"]
    return ["natural modern urban background", "realistic environment", "soft daylight", "subtle depth of field", "visible environmental context"]


def _test_apply_locks(user_text: str, fields: Dict[str, str]) -> None:
    _test_apply_visual_translation_locks(user_text, fields)

    rules = [
        (("中國", "中国"), ["Chinese", "Han Chinese facial features"], ["Japanese", "Taiwanese", "Korean"]),
        (("日本",), ["Japanese", "natural Japanese facial features"], ["Chinese", "Han Chinese", "Taiwanese", "Korean"]),
        (("台灣", "台湾"), ["Taiwanese", "East Asian facial features"], ["Japanese", "Han Chinese", "Korean"]),
        (("韓國", "韩国"), ["Korean", "natural Korean facial features"], ["Japanese", "Chinese", "Han Chinese", "Taiwanese"]),
    ]
    for keywords, required, conflicts in rules:
        if any(k in user_text for k in keywords):
            fields["main_positive"] = _add_terms(_remove_terms(fields["main_positive"], conflicts), required)
            fields["face_positive"] = _add_terms(_remove_terms(fields["face_positive"], conflicts), required)
            break

    portrait_keywords = (
        "肖像", "人像照", "人像攝影", "特寫", "特写", "大頭照", "大头照",
        "頭像", "头像", "證件照", "证件照", "自拍", "近拍臉", "脸部近拍", "胸像",
        "portrait", "headshot", "close-up", "close up", "selfie", "profile picture", "passport photo", "id photo"
    )
    portrait_requested = any(k.lower() in user_text.lower() for k in portrait_keywords)

    if not portrait_requested:
        fields["main_positive"] = _add_terms(_remove_terms(fields["main_positive"], [
            "portrait", "headshot", "close-up", "close up", "bust shot", "shoulder-up", "chest-up", "selfie", "profile picture"
        ]), [
            "medium-long shot", "three-quarter body shot", "visible from head to knees",
            "camera positioned farther away", "more environment visible",
            "balanced subject-to-background composition", "subject not filling the frame",
            "environment clearly readable", "hands visible when reasonable", "not face-focused"
        ])
        fields["main_negative"] = _add_terms(fields["main_negative"], [
            "portrait", "close-up", "extreme close-up", "close-up portrait", "face-only shot", "face-only portrait",
            "headshot", "beauty headshot", "portrait crop", "bust shot", "medium close-up", "shoulder-up shot",
            "shoulder-up crop", "chest-up framing", "chest-up portrait", "tight framing", "zoomed-in face",
            "large face in frame", "face filling the frame", "centered face", "profile picture", "passport photo",
            "ID photo", "studio portrait", "glamour portrait", "beauty portrait"
        ])

    if not _test_has_explicit_background(user_text):
        fields["main_positive"] = _add_terms(fields["main_positive"], _test_infer_background_terms(user_text))
        fields["main_negative"] = _add_terms(fields["main_negative"], [
            "empty background", "blank background", "plain studio backdrop", "blurred unrecognizable environment"
        ])

    if any(k in user_text for k in ("全身照", "完整全身", "全身")):
        fields["main_positive"] = _add_terms(fields["main_positive"], ["full body shot", "entire body visible", "feet visible"])
        fields["main_negative"] = _add_terms(fields["main_negative"], ["cropped feet", "cropped body", "close-up", "headshot"])


MAIN_POSITIVE_FACE_FILLER_TERMS = [
    "harmonious facial proportions",
    "balanced facial features",
    "balanced masculine facial features",
    "refined but realistic facial structure",
    "soft oval face",
    "gentle natural jawline",
    "natural jawline",
    "almond-shaped eyes",
    "clear expressive eyes",
    "balanced eye spacing",
    "realistic eyelid detail",
    "natural eyebrows",
    "softly arched eyebrows",
    "individual eyebrow hairs",
    "proportionate nose bridge",
    "refined natural nose shape",
    "balanced nose proportions",
    "well-shaped natural lips",
    "natural lip contour",
    "subtle cupid's bow",
    "minimal natural makeup",
    "subtle blush",
    "soft natural lip color",
    "natural skin texture",
    "subtle pores",
    "fine skin details",
    "healthy complexion",
    "minimal retouching",
    "soft youthful facial proportions",
    "softly rounded cheeks",
    "gentle facial contour",
    "small delicate chin",
    "slightly round bright eyes",
    "expressive eyes",
    "soft realistic eyelid detail",
    "soft natural eyebrows",
    "delicate natural nose shape",
    "soft natural lips",
    "gentle lip shape",
    "soft natural makeup",
    "fresh blush",
    "delicate lip tint",
    "refined facial structure",
    "elegant facial contour",
    "balanced mature facial proportions",
    "defined but natural jawline",
    "elongated almond eyes",
    "calm refined eyes",
    "elegant eye shape",
    "softly arched natural eyebrows",
    "defined but natural nose bridge",
    "elegant nose shape",
    "refined natural nose tip",
    "refined natural lip shape",
    "elegant lip contour",
    "refined natural makeup",
    "softly defined eye makeup",
    "elegant blush",
    "natural lip color",
    "clean-cut handsome appearance",
    "balanced facial proportions",
    "fresh youthful facial structure",
    "natural facial contour",
    "bright expressive eyes",
    "clear lively eyes",
    "neat natural eyebrows",
    "proportionate natural nose bridge",
    "clean natural nose shape",
    "natural lip shape",
    "balanced lip proportions",
    "approachable expression",
    "mature handsome appearance",
    "defined masculine facial structure",
    "strong natural jawline",
    "composed facial contour",
    "deep-set calm eyes",
    "composed eyes",
    "straight natural eyebrows",
    "well-shaped masculine eyebrows",
    "refined nose bridge",
    "defined natural nose shape",
    "composed lip contour",
    "composed expression",
    "cool mature presence",
    "realistic facial skin",
    "healthy natural skin texture",
]


def _has_any(source: str, terms) -> bool:
    low = str(source or "").lower()
    return any(str(term).lower() in low for term in terms)


def _append_unique(terms: list[str], term: str) -> None:
    if term and term.lower() not in {item.lower() for item in terms}:
        terms.append(term)


def _extract_explicit_main_terms(user_text: str) -> list[str]:
    source = str(user_text or "")
    low = source.lower()
    terms: list[str] = []

    if _has_any(source, ("中國", "中国", "中國人", "中国人", "chinese", "han chinese")):
        _append_unique(terms, "Chinese")

    if _has_any(source, ("年輕女性", "年轻女性", "年輕女人", "年轻女人", "young woman", "young female")):
        _append_unique(terms, "young woman")
    elif _has_any(source, ("女性", "女人", "女生", "女孩子", "woman", "female", "girl")):
        _append_unique(terms, "woman")

    age_match = re.search(r"(\d{1,2})\s*(?:歲|岁|years?\s*old|yo\b)", source, flags=re.IGNORECASE)
    if age_match:
        _append_unique(terms, f"{age_match.group(1)} years old")

    if _has_any(source, ("氣質", "气质", "優雅", "优雅", "elegant beauty")):
        _append_unique(terms, "elegant beauty")
    elif _has_any(source, ("美女", "漂亮", "好看", "正妹", "美麗", "美丽", "beautiful woman", "beautiful girl")):
        _append_unique(terms, "beautiful woman")

    if _has_any(source, ("襯衫", "衬衫", "blouse")):
        _append_unique(terms, "blouse")
    elif _has_any(source, ("shirt",)):
        _append_unique(terms, "shirt")

    if _has_any(source, ("短裙", "short skirt", "mini skirt", "miniskirt")):
        _append_unique(terms, "short skirt")

    if (
        _has_any(source, ("稀疏空氣瀏海", "稀疏空气刘海", "稀疏的空氣瀏海", "稀疏的空气刘海", "sparse air刘海", "sparse wispy air bangs"))
        or ("稀疏" in source and _has_any(source, ("瀏海", "刘海", "bangs")))
    ):
        _append_unique(terms, "sparse wispy air bangs")
    elif _has_any(source, ("空氣瀏海", "空气刘海", "air刘海", "wispy air bangs")):
        _append_unique(terms, "wispy air bangs")
    elif _has_any(source, ("瀏海", "刘海", "bangs")):
        _append_unique(terms, "bangs")

    normalized_source = _test_normalize_visual_terms(source)
    if _has_claw_clip_updo_request(source) or _has_claw_clip_updo_request(normalized_source):
        _append_unique(terms, "compact rounded claw clip updo at the back of the head")
        _append_unique(terms, "all long hair gathered upward and secured with a claw hair clip")
        _append_unique(terms, "bun-like shape but not a formal bun")
        _append_unique(terms, "no loose hanging hair tail")

    right_hand_hair = (
        ("右手" in source and _has_any(source, ("右耳", "耳邊", "耳边", "髮絲", "发丝", "頭髮", "头发", "hair")))
        or _has_any(low, ("right hand adjusting hair", "right hand fixing hair", "right hand touching hair"))
    )
    if right_hand_hair:
        _append_unique(terms, "right hand adjusting hair by ear")

    if (
        ("左手" in source and _has_any(source, ("書", "书", "book")))
        or _has_any(low, ("left hand holding a book",))
    ):
        _append_unique(terms, "left hand holding a book")
    elif _has_any(source, ("拿著一本書", "拿着一本书", "holding a book")):
        _append_unique(terms, "holding a book")

    if _has_any(source, ("走在校園", "走在校园", "walking in campus", "walking on campus")):
        _append_unique(terms, "walking in campus")
    elif _has_any(source, ("校園", "校园", "campus")):
        _append_unique(terms, "campus")

    if _has_any(source, ("校園建築", "校园建筑", "campus buildings")):
        _append_unique(terms, "campus buildings")

    return terms


def _prepend_terms(text: str, terms: list[str]) -> str:
    body = _remove_terms(text, terms)
    return ", ".join([item for item in [*terms, body] if item])


def _apply_test_machine_source_overlay(user_text: str, fields: Dict[str, str]) -> None:
    fields["main_positive"] = _remove_terms(
        fields.get("main_positive"),
        MAIN_POSITIVE_FACE_FILLER_TERMS,
    )
    if not _has_any(user_text, ("全身照", "完整全身", "全身", "full body", "entire body", "feet visible")):
        fields["main_positive"] = _remove_terms(
            fields["main_positive"],
            ["full body shot", "entire body visible", "feet visible"],
        )
    explicit_terms = _extract_explicit_main_terms(user_text)
    if explicit_terms:
        fields["main_positive"] = _prepend_terms(fields["main_positive"], explicit_terms)


def _post_generate(
    *,
    model: str,
    prompt: str,
    system: str = "",
    num_predict: int = 512,
    temperature: float = 0.6,
    format_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": float(temperature),
            "num_predict": int(num_predict),
            "num_ctx": 8192,
        },
    }
    if format_schema:
        payload["format"] = format_schema
    if gateway_requested() and not gateway_enabled():
        if gateway_reverse_enabled():
            try:
                task_id = create_local_ai_task("ollama_generate", payload)
                waited = wait_for_local_ai_task_result(
                    task_id,
                    timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
                    poll_seconds=2,
                )
            except Exception as exc:
                return {"ok": False, "message": f"建立 Qwen worker 任務失敗：{exc}"}
            if not waited.get("ok") or not waited.get("bytes"):
                return {"ok": False, "message": waited.get("message") or "Qwen worker 沒有回傳結果"}
            try:
                data = json.loads(waited["bytes"].decode("utf-8"))
            except Exception as exc:
                return {"ok": False, "message": f"Qwen worker JSON 解析失敗：{exc}"}
        else:
            return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}

    elif gateway_enabled():
        gateway_result = gateway_post_json(
            "/v1/ollama/generate",
            payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        if not gateway_result.get("ok"):
            return {"ok": False, "message": gateway_result.get("message") or "Qwen 閘道呼叫失敗"}
        data = gateway_result.get("data") or {}
    else:
        try:
            response = _OLLAMA_SESSION.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 連線失敗：{exc}"}

        if not response.ok:
            return {"ok": False, "message": f"Ollama HTTP {response.status_code}: {response.text[:500]}"}

        try:
            data = response.json()
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 回傳 JSON 解析失敗：{exc}"}

    text = _clean_text(data.get("response"))
    return {
        "ok": bool(text),
        "text": text,
        "raw": data,
        "message": None if text else "Ollama 沒有回傳文字",
    }


def _post_chat(
    *,
    model: str,
    user_text: str,
    system: str = "",
    num_predict: int = 512,
    temperature: float = 0.6,
    format_schema: Optional[Dict[str, Any]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    if cancel_check and cancel_check():
        return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}

    url = f"{OLLAMA_BASE_URL}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": str(user_text or "")})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": float(temperature),
            "num_predict": int(num_predict),
            "num_ctx": 8192,
        },
    }
    if format_schema:
        payload["format"] = format_schema

    if gateway_requested() and not gateway_enabled():
        if gateway_reverse_enabled():
            try:
                task_id = create_local_ai_task("ollama_chat", payload)
                waited = wait_for_local_ai_task_result(
                    task_id,
                    timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
                    poll_seconds=2,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                return {"ok": False, "message": f"建立 Qwen worker 任務失敗：{exc}"}
            if waited.get("canceled"):
                return {
                    "ok": False,
                    "canceled": True,
                    "message": waited.get("message") or "使用者已取消生圖",
                    "local_task_id": task_id,
                }
            if not waited.get("ok") or not waited.get("bytes"):
                return {"ok": False, "message": waited.get("message") or "Qwen worker 沒有回傳結果"}
            try:
                data = json.loads(waited["bytes"].decode("utf-8"))
            except Exception as exc:
                return {"ok": False, "message": f"Qwen worker JSON 解析失敗：{exc}"}
        else:
            return {"ok": False, "message": gateway_config_error() or "本機 AI 閘道設定不完整"}

    elif gateway_enabled():
        gateway_result = gateway_post_json(
            "/v1/ollama/chat",
            payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        if not gateway_result.get("ok"):
            return {"ok": False, "message": gateway_result.get("message") or "Qwen 閘道呼叫失敗"}
        data = gateway_result.get("data") or {}
    else:
        try:
            response = _OLLAMA_SESSION.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 連線失敗：{exc}"}

        if not response.ok:
            return {"ok": False, "message": f"Ollama HTTP {response.status_code}: {response.text[:500]}"}

        try:
            data = response.json()
        except Exception as exc:
            return {"ok": False, "message": f"Ollama 回傳 JSON 解析失敗：{exc}"}

    message = data.get("message") or {}
    text = _clean_text(message.get("content") or data.get("response"))
    if cancel_check and cancel_check():
        return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}
    return {
        "ok": bool(text),
        "text": text,
        "raw": data,
        "message": None if text else "Ollama 沒有回傳文字",
    }


def get_secondary_model_label() -> str:
    return OLLAMA_DEPUTY_MODEL


def generate_chat_reply(
    *,
    prompt: str,
    history=None,
    user_text=None,
    debug_context=None,
    stop_event=None,
) -> Dict[str, Any]:
    if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
        return {"ok": False, "message": "副模型已取消"}

    result = _post_generate(
        model=OLLAMA_DEPUTY_MODEL,
        prompt=str(prompt or ""),
        system="",
        num_predict=OLLAMA_CHAT_NUM_PREDICT,
        temperature=0.75,
    )
    if not result.get("ok"):
        return {"ok": False, "message": result.get("message") or "Qwen 沒有回傳結果", "model": OLLAMA_DEPUTY_MODEL}

    return {
        "ok": True,
        "text": result.get("text"),
        "model": OLLAMA_DEPUTY_MODEL,
    }


def _strip_code_fence(text: str) -> str:
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = _strip_code_fence(text)
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _infer_identity(text: str) -> str:
    source = str(text or "").lower()
    if any(token in source for token in ["台灣", "taiwan", "taiwanese"]):
        return "Taiwanese"
    if any(token in source for token in ["日本", "japan", "japanese"]):
        return "Japanese"
    if any(token in source for token in ["韓國", "韩国", "korea", "korean"]):
        return "Korean"
    if any(token in source for token in ["中國", "中国", "china", "chinese", "han chinese"]):
        return "Chinese"
    if any(token in source for token in ["歐美", "欧美", "western", "caucasian", "european"]):
        return "Western"
    return "EastAsian"


def _infer_gender(text: str, gender_hint: str = "") -> str:
    hint = str(gender_hint or "").strip().lower()
    if hint in {"male", "man", "boy", "男性", "男"}:
        return "man"
    if hint in {"female", "woman", "girl", "女性", "女"}:
        return "woman"

    source = str(text or "").lower()
    if any(token in source for token in ["男", " male ", " man", "boy", "gentleman"]):
        return "man"
    return "woman"


def build_face_prompts(face_identity: str, face_gender: str) -> Tuple[str, str]:
    identity = _clean_text(face_identity) or "EastAsian"
    gender = _clean_text(face_gender).lower() or "woman"
    if gender not in {"woman", "man"}:
        gender = "woman"

    prefix = FACE_IDENTITY_PREFIX.get((identity, gender))
    if not prefix:
        readable_gender = "woman" if gender == "woman" else "man"
        prefix = f"young {identity} {readable_gender}, natural facial features, natural facial structure"

    return f"{prefix}, {FACE_SUFFIX}", FACE_NEGATIVE


def organize_image_prompt(draft_prompt: str, gender_hint: str = "", **kwargs) -> Dict[str, Any]:
    user_text = _clean_text(draft_prompt)
    if not user_text:
        return {"ok": False, "message": "原始提示詞為空"}
    cancel_check = kwargs.get("cancel_check")
    progress_callback = kwargs.get("progress_callback")
    if callable(cancel_check) and cancel_check():
        return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}

    result = _post_chat(
        model=OLLAMA_PROMPT_MODEL,
        user_text=user_text,
        system=IMAGE_PROMPT_SYSTEM,
        num_predict=OLLAMA_PROMPT_NUM_PREDICT,
        temperature=0.2,
        format_schema=IMAGE_PROMPT_SCHEMA,
        cancel_check=cancel_check if callable(cancel_check) else None,
        progress_callback=progress_callback if callable(progress_callback) else None,
    )
    if result.get("canceled"):
        return {"ok": False, "canceled": True, "message": result.get("message") or "使用者已取消生圖"}
    if not result.get("ok"):
        return {"ok": False, "message": result.get("message") or "Qwen Prompt 整理失敗"}

    parsed = _extract_json(result.get("text")) or {}
    fields: Dict[str, str] = {}
    for key in IMAGE_PROMPT_KEYS:
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip():
            return {"ok": False, "message": f"Qwen 缺少欄位：{key}"}
        fields[key] = " ".join(value.strip().split())

    _apply_test_machine_source_overlay(user_text, fields)
    _test_apply_locks(user_text, fields)
    _apply_test_machine_source_overlay(user_text, fields)
    face_identity = _infer_identity(user_text)
    face_gender = _infer_gender(user_text, gender_hint)

    assembled = (
        f"main_positive: {fields['main_positive']}\n"
        f"main_negative: {fields['main_negative']}\n"
        f"face_positive: {fields['face_positive']}\n"
        f"face_negative: {fields['face_negative']}"
    )
    return {
        "ok": True,
        "model": OLLAMA_PROMPT_MODEL,
        "main_positive": fields["main_positive"],
        "main_negative": fields["main_negative"],
        "face_identity": face_identity,
        "face_gender": face_gender,
        "face_positive": fields["face_positive"],
        "face_negative": fields["face_negative"],
        "text": fields["main_positive"],
        "preview_text": assembled,
        "raw_text": result.get("text") or "",
    }
