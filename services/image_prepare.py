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
MIN_DIMENSION = 256
DIMENSION_STEP = 64
PAD_COLOR = (240, 240, 240)


def _round_down_to_step(value: float, step: int = DIMENSION_STEP, minimum: int = MIN_DIMENSION) -> int:
    rounded = int(value) // int(step) * int(step)
    return max(int(minimum), rounded)


def _choose_dynamic_output_size(original_width: int, original_height: int) -> Tuple[int, int]:
    """依原圖比例，挑選不超過安全像素量的最大 64 倍數尺寸。"""
    if original_width <= 0 or original_height <= 0:
        return OUTPUT_WIDTH, OUTPUT_HEIGHT

    ratio = float(original_width) / float(original_height)
    target_height = sqrt(MAX_SAFE_PIXELS / ratio)
    target_width = target_height * ratio

    width = _round_down_to_step(target_width)
    height = _round_down_to_step(target_height)

    # 若四捨五入後仍超過總像素，就持續往下收。
    while width * height > MAX_SAFE_PIXELS and width > DIMENSION_STEP and height > DIMENSION_STEP:
        if width >= height:
            width -= DIMENSION_STEP
        else:
            height -= DIMENSION_STEP

    width = max(DIMENSION_STEP, width)
    height = max(DIMENSION_STEP, height)
    return width, height


def prepare_img2img_source(
    source_image_bytes: bytes,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
) -> Dict[str, Any]:
    """
    來源圖預處理：
    - 保留完整比例
    - 依原圖比例自動挑選安全輸出尺寸
    - 等比例縮放，不裁切
    - 用淺灰色補邊，方便模型後續改寫
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
    }
