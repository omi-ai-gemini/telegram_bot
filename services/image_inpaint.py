from io import BytesIO
from typing import Any, Dict, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageStat


# 最終輸出畫布尺寸。基準圖只會等比例放入，不會拉伸。
OUTPUT_WIDTH = 896
OUTPUT_HEIGHT = 1152


def _border_color(image: Image.Image) -> Tuple[int, int, int]:
    """從原圖四周估算底色，讓等比例置中的留白不會出現突兀色塊。"""
    rgb = image.convert("RGB")
    band = max(2, min(rgb.size) // 80)
    strips = [
        rgb.crop((0, 0, rgb.width, band)),
        rgb.crop((0, rgb.height - band, rgb.width, rgb.height)),
        rgb.crop((0, 0, band, rgb.height)),
        rgb.crop((rgb.width - band, 0, rgb.width, rgb.height)),
    ]
    sample = Image.new("RGB", (sum(part.width for part in strips), max(part.height for part in strips)), (232, 232, 232))
    x = 0
    for part in strips:
        sample.paste(part, (x, 0))
        x += part.width
    mean = ImageStat.Stat(sample).median
    return tuple(max(0, min(255, int(value))) for value in mean[:3])


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _identity_anchor_mask(
    canvas_size: Tuple[int, int],
    fitted_box: Tuple[int, int, int, int],
) -> Image.Image:
    """
    建立 AI Horde inpainting 遮罩：
    - 白色：允許模型依提示詞重繪，包括身體、服裝、姿勢與場景。
    - 黑色：保留臉部核心特徵，避免基準人物完全消失。
    - 灰階羽化：降低臉部與新畫面的接縫感。

    基準圖是置中的正面人物照，因此身份錨點放在上方中央臉部區域。
    """
    width, height = canvas_size
    left, top, fitted_width, fitted_height = fitted_box

    mask = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(mask)

    # 外圈保留頭部輪廓一部分，內圈保留五官核心。
    outer = (
        left + int(fitted_width * 0.31),
        top + int(fitted_height * 0.035),
        left + int(fitted_width * 0.69),
        top + int(fitted_height * 0.325),
    )
    inner = (
        left + int(fitted_width * 0.385),
        top + int(fitted_height * 0.075),
        left + int(fitted_width * 0.615),
        top + int(fitted_height * 0.265),
    )

    draw.ellipse(outer, fill=88)
    draw.ellipse(inner, fill=0)

    # 羽化邊緣，避免生成後像貼上一張臉。
    blur_radius = max(8, round(min(width, height) * 0.014))
    return mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))


def prepare_inpainting_assets(source_image_bytes: bytes) -> Dict[str, Any]:
    """
    將任意基準圖轉成 AI Horde inpainting 使用的來源圖與遮罩。

    重點：
    1. 最終畫布固定 896×1152。
    2. 基準圖等比例縮放後置中，絕不改變人物長寬比例。
    3. 身體、衣服、姿勢與背景允許依 prompt 重繪；臉部保留身份錨點。
    """
    if not source_image_bytes:
        raise ValueError("基準圖內容為空")

    try:
        with Image.open(BytesIO(source_image_bytes)) as opened:
            original = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception as exc:
        raise ValueError(f"基準圖無法讀取：{exc}") from exc

    if original.width < 32 or original.height < 32:
        raise ValueError("基準圖尺寸過小")

    canvas_size = (OUTPUT_WIDTH, OUTPUT_HEIGHT)
    fitted = ImageOps.contain(original, canvas_size, method=Image.Resampling.LANCZOS)
    left = (OUTPUT_WIDTH - fitted.width) // 2
    top = (OUTPUT_HEIGHT - fitted.height) // 2

    canvas = Image.new("RGB", canvas_size, _border_color(original))
    canvas.paste(fitted, (left, top))

    fitted_box = (left, top, fitted.width, fitted.height)
    mask = _identity_anchor_mask(canvas_size, fitted_box)

    return {
        "source_image_bytes": _png_bytes(canvas),
        "source_mask_bytes": _png_bytes(mask),
        "source_mime_type": "image/png",
        "mask_mime_type": "image/png",
        "width": OUTPUT_WIDTH,
        "height": OUTPUT_HEIGHT,
        "original_size": original.size,
        "fitted_size": fitted.size,
        "fitted_offset": (left, top),
    }
