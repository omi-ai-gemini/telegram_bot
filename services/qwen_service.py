import json
import os
import re
from typing import Any, Dict, Optional, Tuple

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
你是 Telemini 的圖片提示詞整理器。

你只把使用者需求忠實整理為 ComfyUI／SDXL 可用的四組英文提示詞，並只輸出 JSON。這是純文生圖流程，沒有參考圖。

固定欄位：
main_positive：人物、國籍或族群、性別、外觀、服裝或裸體狀態、動作、表情、構圖、背景、光線、寫實攝影風格。
main_negative：使用者禁止內容、錯誤構圖、錯誤衣物、錯誤族群特徵、低品質、肢體與手部錯誤、塑膠皮膚、動畫或插畫風。
face_positive：只寫臉部生成與修復需要的性別、年齡感、臉型、眼睛、眉毛、鼻子、嘴唇、妝容、膚質與自然五官品質。
face_negative：只寫臉部錯誤，例如鬥雞眼、不對稱眼睛、錯誤或額外瞳孔、臉部比例失衡、假睫毛、假眉毛、塑膠皮膚、過度磨皮、臉部變形與模糊。

硬性規則：
1. 使用者明確指定的國籍、族群、性別、年齡、外貌、臉型、眼睛、鼻子、嘴唇、妝容、構圖、服裝、背景、動作、表情與禁止項目，全部都是鎖定值，不可自行替換。
2. 美感詞庫只用來補使用者未指定的部位，不可覆蓋使用者明確要求。
3. 同一次輸出只能選一套一致的美感方向，不可把自然、甜美、成熟三套互相混成拼裝臉。
4. 使用者只說「美女、漂亮、好看、正妹、美麗」而沒有細分外貌時，使用自然耐看型預設。
5. 使用者說「可愛、甜美、清純、甜妹」時，使用甜美可愛型預設。
6. 使用者說「成熟、氣質、冷感、御姐、優雅」時，使用成熟精緻型預設。
7. 使用者只說「帥哥、帥氣、好看的男人」而沒有細分外貌時，使用男性自然耐看型預設。
8. 使用者說「陽光、清爽、鄰家、年輕、少年感」時，使用男性陽光清爽型預設。
9. 使用者說「成熟、冷峻、菁英、霸氣、總裁感」時，使用男性成熟冷峻型預設。
10. 預設禁止肖像照與大頭構圖。除非使用者明確要求肖像、特寫、大頭照、自拍、證件照、個人頭像、臉部近拍或胸像，main_positive 必須加入 medium-long shot, three-quarter body shot, visible from head to knees, camera positioned farther away, more environment visible, balanced subject-to-background composition, subject not filling the frame, environment clearly readable, hands visible when reasonable；main_negative 必須加入 portrait, close-up, extreme close-up, close-up portrait, face-only shot, face-only portrait, headshot, beauty headshot, portrait crop, bust shot, medium close-up, shoulder-up shot, shoulder-up crop, chest-up framing, chest-up portrait, tight framing, zoomed-in face, large face in frame, face filling the frame, centered face, profile picture, passport photo, ID photo, studio portrait, glamour portrait, beauty portrait。
11. 若使用者沒有指定背景或場景，必須依據人物服裝、動作、氣氛、時間、天氣與主題，自動補一個適合且不搶主體的真實背景；不要留成空白背景，也不要只給模糊散景。若仍無足夠線索，再使用自然、乾淨、可閱讀的日常真實環境。
12. 若使用者沒有指定動作，補 natural standing pose；若沒有指定表情，補 relaxed natural expression。
13. 使用者說不要特寫時，main_positive 必須包含 three-quarter body shot, medium-long shot, visible from head to knees, camera positioned farther away；main_negative 必須包含 close-up, extreme close-up, headshot, face-only shot, tight framing, face filling the frame。
14. 使用者說全身時，main_positive 必須包含 full body shot, entire body visible, feet visible；main_negative 必須包含 cropped feet, cropped body, close-up, headshot。
15. 不要編造使用者未要求的服裝、物品、國籍或劇情。
16. 四欄都只使用英文逗號分隔提示詞，不寫解釋、故事、標題或 Markdown。

中文詞彙翻譯鎖定：
1. 瀏海、刘海、air刘海、空氣瀏海、空气刘海要翻成 bangs；稀疏空氣瀏海、稀疏空气刘海、sparse air刘海要翻成 sparse wispy air bangs，不可保留中文或中英混字。
2. 鯊魚夾、鲨鱼夹、shark clip 要翻成 claw hair clip。
3. 使用者描述「把長髮整理起來放在腦後用鯊魚夾夾起來」或類似意思時，不是垂下來的馬尾，不是一束頭髮，也不是正式包包頭；要翻成 compact rounded claw clip updo at the back of the head, all long hair gathered upward and secured with a claw hair clip, bun-like shape but not a formal bun, no loose hanging hair tail。
4. 翻譯後不得留下 瀏海、刘海、鯊魚夾、鲨鱼夹、air刘海、shark clip 這類原字樣。

美感詞庫：

A. 自然耐看型（女性預設）
臉型與比例：harmonious facial proportions, balanced facial features, refined but realistic facial structure, soft oval face, gentle natural jawline
眼睛：almond-shaped eyes, clear expressive eyes, balanced eye spacing, realistic eyelid detail
眉毛：natural eyebrows, softly arched eyebrows, individual eyebrow hairs
鼻子：proportionate nose bridge, refined natural nose shape, balanced nose proportions
嘴唇：well-shaped natural lips, natural lip contour, subtle cupid's bow
妝容：minimal natural makeup, subtle blush, soft natural lip color
皮膚：natural skin texture, subtle pores, fine skin details, healthy complexion, minimal retouching

B. 甜美可愛型
臉型與比例：soft youthful facial proportions, softly rounded cheeks, gentle facial contour, small delicate chin
眼睛：slightly round bright eyes, expressive eyes, soft realistic eyelid detail
眉毛：soft natural eyebrows, individual eyebrow hairs
鼻子：delicate natural nose shape, balanced nose proportions
嘴唇：soft natural lips, gentle lip shape, subtle cupid's bow
妝容：soft natural makeup, fresh blush, delicate lip tint
皮膚：natural skin texture, subtle pores, fine skin details, healthy complexion

C. 成熟精緻型
臉型與比例：refined facial structure, elegant facial contour, balanced mature facial proportions, defined but natural jawline
眼睛：elongated almond eyes, calm refined eyes, elegant eye shape, realistic eyelid detail
眉毛：softly arched natural eyebrows, individual eyebrow hairs
鼻子：defined but natural nose bridge, elegant nose shape, refined natural nose tip
嘴唇：refined natural lip shape, elegant lip contour
妝容：refined natural makeup, softly defined eye makeup, elegant blush, natural lip color
皮膚：natural skin texture, subtle pores, fine skin details, minimal retouching

D. 男性自然耐看型（男性預設）
臉型與比例：harmonious facial proportions, balanced masculine facial features, refined but realistic facial structure, natural jawline
眼睛：clear expressive eyes, balanced eye spacing, realistic eyelid detail
眉毛：natural well-shaped eyebrows, individual eyebrow hairs
鼻子：proportionate nose bridge, refined natural nose shape, balanced nose proportions
嘴唇：well-shaped natural lips, balanced lip proportions
皮膚：healthy natural skin texture, subtle pores, realistic facial skin

E. 男性陽光清爽型
臉型與比例：clean-cut handsome appearance, balanced facial proportions, fresh youthful facial structure, natural facial contour
眼睛：bright expressive eyes, clear lively eyes, realistic eyelid detail
眉毛：neat natural eyebrows, individual eyebrow hairs
鼻子：proportionate natural nose bridge, clean natural nose shape
嘴唇：natural lip shape, balanced lip proportions
表情與氣質：natural smile, approachable expression
皮膚：healthy complexion, natural skin texture, subtle pores

F. 男性成熟冷峻型
臉型與比例：mature handsome appearance, defined masculine facial structure, strong natural jawline, composed facial contour
眼睛：deep-set calm eyes, composed eyes, realistic eyelid detail
眉毛：straight natural eyebrows, well-shaped masculine eyebrows
鼻子：refined nose bridge, defined natural nose shape
嘴唇：well-shaped natural lips, composed lip contour
表情與氣質：composed expression, cool mature presence
皮膚：realistic facial skin, healthy natural skin texture, subtle pores

補值限制：
1. 每個未指定部位只補少量最核心的詞，不要把整個詞庫全部塞滿。
2. 臉型、眼睛、鼻子、嘴唇各最多選 1 至 2 個描述；妝容最多 2 個；皮膚最多 3 個。
3. 不要自動加入誇張大眼、極尖下巴、極小鼻子、厚重眼妝、網紅模板臉或不自然整形感。
4. 使用者沒有說漂亮或帥氣時，也可以補基本自然品質，但不要擅自把人物改造成強烈明星臉。
5. main_positive 寫整體外貌與場景；face_positive 寫臉部細節。避免兩欄大量重複。

固定 face_negative 建議至少包含：
cross-eyed, asymmetrical eyes, mismatched eyes, malformed pupils, extra pupils, fake eyelashes, thick clumped eyelashes, overly long eyelashes, painted eyelashes, heavy eyeliner, painted eyebrows, blocky eyebrows, eyebrow tattoo, awkward facial proportions, distorted facial structure, plastic skin, over-smoothed skin, airbrushed skin, waxy skin, deformed face, blurry face, low quality

固定 main_negative 建議至少包含：
anime, cartoon, illustration, low quality, blurry, bad anatomy, deformed hands, extra fingers, missing fingers, distorted limbs, plastic skin, over-smoothed skin, generic AI face

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
) -> Dict[str, Any]:
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
    if not gender_hint:
        gender_hint = str(kwargs.get("gender") or kwargs.get("gender_hint") or "")
    clean_draft = _normalize_visual_terms(draft_prompt)
    if not clean_draft:
        return {"ok": False, "message": "原始提示詞為空"}

    prompt = clean_draft
    if str(gender_hint or "").strip():
        prompt = f"{prompt}\n\n性別提示：{str(gender_hint or '').strip()}"

    result = _post_chat(
        model=OLLAMA_PROMPT_MODEL,
        user_text=prompt,
        system=IMAGE_PROMPT_SYSTEM,
        num_predict=OLLAMA_PROMPT_NUM_PREDICT,
        temperature=0.2,
        format_schema=IMAGE_PROMPT_SCHEMA,
    )
    if not result.get("ok"):
        return {"ok": False, "message": result.get("message") or "Qwen Prompt 整理失敗"}

    parsed = _extract_json(result.get("text")) or {}
    main_positive = _normalize_visual_terms(
        parsed.get("main_positive")
        or parsed.get("positive_prompt")
        or parsed.get("final_positive_prompt")
    )
    main_negative = _clean_text(
        parsed.get("main_negative")
        or parsed.get("negative_prompt")
        or parsed.get("final_negative_prompt")
    )
    face_positive = _normalize_visual_terms(
        parsed.get("face_positive")
        or parsed.get("face_prompt")
        or parsed.get("face_detailer_positive")
    )
    face_negative = _clean_text(
        parsed.get("face_negative")
        or parsed.get("face_negative_prompt")
        or parsed.get("face_detailer_negative")
    )
    face_identity = _clean_text(parsed.get("face_identity") or parsed.get("identity")) or _infer_identity(clean_draft)
    face_gender = _clean_text(parsed.get("face_gender") or parsed.get("gender")) or _infer_gender(clean_draft, gender_hint)

    if face_identity not in {"Chinese", "Japanese", "Korean", "Taiwanese", "Western", "EastAsian"}:
        face_identity = _infer_identity(face_identity or clean_draft)
    if face_gender.lower() not in {"woman", "man"}:
        face_gender = _infer_gender(face_gender or clean_draft, gender_hint)
    else:
        face_gender = face_gender.lower()

    if not main_positive:
        return {"ok": False, "message": "Qwen 沒有輸出可用的 main_positive"}

    if not main_negative:
        main_negative = (
            "close-up, extreme close-up, headshot, face-only shot, portrait crop, upper-face crop, "
            "zoomed-in face, tight framing, cropped body, face filling the frame, anime, cartoon, "
            "illustration, blurry, low quality, deformed face, bad anatomy, extra limbs, plastic skin"
        )

    fallback_face_positive, fallback_face_negative = build_face_prompts(face_identity, face_gender)
    if not face_positive:
        face_positive = fallback_face_positive
    if not face_negative:
        face_negative = fallback_face_negative

    fields = {
        "main_positive": main_positive,
        "main_negative": main_negative,
        "face_positive": face_positive,
        "face_negative": face_negative,
    }
    _apply_visual_translation_locks(clean_draft, fields)
    _apply_identity_and_composition_locks(clean_draft, fields)

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
