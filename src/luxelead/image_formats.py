"""Supported image formats and HEIC/HEIF decoding for Pillow."""

from PIL import Image, ImageOps

IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
)

_heic_registered = False


def register_heic_support() -> bool:
    """Register HEIC/HEIF opener with Pillow. Returns True if available."""
    global _heic_registered
    if _heic_registered:
        return True
    try:
        from pi_heif import register_heif_opener

        register_heif_opener()
        _heic_registered = True
        return True
    except ImportError:
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
            _heic_registered = True
            return True
        except ImportError:
            return False


def is_image_file(filename: str) -> bool:
    return filename.lower().endswith(IMAGE_EXTENSIONS)


def open_image_for_ppt(path: str) -> Image.Image:
    """Open image with EXIF/HEIF orientation baked into pixels (matches viewer display)."""
    register_heic_support()
    img = Image.open(path)
    return ImageOps.exif_transpose(img)


def save_rgb_jpeg(img: Image.Image, path: str, quality: int = 95) -> None:
    """Save as JPEG without EXIF orientation so PowerPoint won't rotate again."""
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        rgb = background
    elif img.mode != "RGB":
        rgb = img.convert("RGB")
    else:
        rgb = img
    rgb.save(path, "JPEG", quality=quality, exif=b"")
