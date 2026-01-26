"""
Utility functions for image loading.
"""

from io import BytesIO

from PIL import Image


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """
    Load image from bytes.

    Args:
        image_bytes: Image file bytes

    Returns:
        PIL Image object in RGB format
    """
    image = Image.open(BytesIO(image_bytes))

    # Convert to RGB if needed
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    return image
