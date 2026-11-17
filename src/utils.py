"""Bounded image loading and camera orientation normalization."""

from io import BytesIO
from PIL import Image, ImageOps
from src.config import settings
from src.dates import normalise_date  # noqa: F401 (compatibility for callers)


class ImageTooLarge(ValueError):
    pass


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    if len(image_bytes) > settings.max_upload_bytes:
        raise ImageTooLarge("Image exceeds the upload byte limit")
    with Image.open(BytesIO(image_bytes)) as source:
        if source.width * source.height > settings.max_image_pixels:
            raise ImageTooLarge("Image exceeds the decoded pixel limit")
        source.load()  # Invalid/truncated RGB files must fail here, not in the backend.
        image = ImageOps.exif_transpose(source)
        return image.convert("RGB")
