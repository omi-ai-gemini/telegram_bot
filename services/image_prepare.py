from io import BytesIO
from math import sqrt
from typing import Any, Dict, Tuple

try:
    from PIL import Image, ImageOps
    _PIL_IMPORT_ERROR = None
except ImportError as exc:
    Image = None
    ImageOps = None
    _PIL_IMPORT_ERROR = exc


OUTPUT_WIDTH = 896
OUTPUT_HEIGHT = 1152
MAX_SAFE_PIXELS = 1024 * 1024
MAX_OUTPUT_SIDE = 1024
MIN_OUTPUT_SIDE = 512
MAX_CANVAS_ASPECT_RATIO = 2.0
DIMENSION_STEP = 64
PAD_COLOR = (240, 240, 240)


def _round_to_step(value: float, step: int = DIMENSION_STEP) -> int:
    """四捨五入到最接近的 64 倍數。"""
    return max(int(step), int((float(value) + (step / 2)) // step) * int(step))


def _choose_dynamic_output_size(original_width: int, original_height: int) -> Tuple[int, int]:
    """
    挑選 AI Horde 工作節點較容易接受的圖生圖畫布。

    規則：
    - 最長邊不超過 1024。
    - 畫布長寬比不超過 2:1；超長圖改用補邊，不裁切原圖。
    - 寬高維持 64 的倍數。
    - 總像素不超過 1024×1024。
    """
    if original_width <= 0 or original_height <= 0:
        return 768, 1024

    original_ratio = float(original_width) / float(original_height)
    min_ratio = 1.0 / MAX_CANVAS_ASPECT_RATIO
    canvas_ratio = max(min_ratio, min(MAX_CANVAS_ASPECT_RATIO, original_ratio))

    if canvas_ratio >= 1.0:
        width = MAX_OUTPUT_SIDE
        height = _round_to_step(width / canvas_ratio)
    else:
        height = MAX_OUTPUT_SIDE
        width = _round_to_step(height * canvas_ratio)

    width = max(MIN_OUTPUT_SIDE, min(MAX_OUTPUT_SIDE, width))
    height = max(MIN_OUTPUT_SIDE, min(MAX_OUTPUT_SIDE, height))

    # 保險：若因取整超過安全像素，逐步縮短較長的一邊。
    while width * height > MAX_SAFE_PIXELS:
        if width >= height and width > MIN_OUTPUT_SIDE:
            width -= DIMENSION_STEP
        elif height > MIN_OUTPUT_SIDE:
            height -= DIMENSION_STEP
        else:
            break

    return int(width), int(height)


def prepare_img2img_source(
    source_image_bytes: bytes,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
) -> Dict[str, Any]:
    """
    來源圖預處理：
    - 保留完整原圖內容
    - 使用最長邊 1024、最大 2:1 的相容畫布
    - 等比例縮放，不裁切
    - 超長或超寬圖片使用淺灰色補邊
    """
    if _PIL_IMPORT_ERROR is not None:
        raise RuntimeError(
            "圖生圖來源處理缺少 Pillow，請確認 requirements.txt 已包含 Pillow==12.3.0"
        ) from _PIL_IMPORT_ERROR

    if not source_image_bytes:
        raise ValueError("參考圖片內容為空")

    try:
        with Image.open(BytesIO(source_image_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            original_size = image.size
            dynamic_width, dynamic_height = _choose_dynamic_output_size(*original_size)

            contained = ImageOps.contain(
                image,
                (int(dynamic_width), int(dynamic_height)),
                method=Image.Resampling.LANCZOS,
            )

            canvas = Image.new("RGB", (int(dynamic_width), int(dynamic_height)), PAD_COLOR)
            paste_x = (dynamic_width - contained.width) // 2
            paste_y = (dynamic_height - contained.height) // 2
            canvas.paste(contained, (paste_x, paste_y))
    except Exception as exc:
        raise ValueError("參考圖片無法讀取，請改用 JPG、PNG 或 WEBP") from exc

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)

    return {
        "bytes": output.getvalue(),
        "mime_type": "image/png",
        "original_size": original_size,
        "output_size": canvas.size,
        "content_size": contained.size,
        "pad_color": PAD_COLOR,
        "max_safe_pixels": MAX_SAFE_PIXELS,
        "max_output_side": MAX_OUTPUT_SIDE,
        "max_canvas_aspect_ratio": MAX_CANVAS_ASPECT_RATIO,
    }
