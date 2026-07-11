from io import BytesIO
from typing import Any, Dict

try:
    from PIL import Image, ImageOps
    _PIL_IMPORT_ERROR = None
except ImportError as exc:
    Image = None
    ImageOps = None
    _PIL_IMPORT_ERROR = exc


OUTPUT_WIDTH = 896
OUTPUT_HEIGHT = 1152


def prepare_img2img_source(
    source_image_bytes: bytes,
    width: int = OUTPUT_WIDTH,
    height: int = OUTPUT_HEIGHT,
) -> Dict[str, Any]:
    """把來源圖等比例縮放與裁切到最終畫布，禁止直接拉伸人物。"""
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
            fitted = ImageOps.fit(
                image,
                (int(width), int(height)),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
    except Exception as exc:
        raise ValueError("參考圖片無法讀取，請改用 JPG、PNG 或 WEBP") from exc

    output = BytesIO()
    fitted.save(output, format="PNG", optimize=True)
    return {
        "bytes": output.getvalue(),
        "mime_type": "image/png",
        "original_size": original_size,
        "output_size": fitted.size,
    }
