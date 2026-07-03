"""Video aspect-ratio and output-resolution conventions."""

LANDSCAPE = "landscape"
PORTRAIT = "portrait"

VIDEO_RESOLUTIONS: dict[str, tuple[int, int]] = {
    LANDSCAPE: (1920, 1080),
    PORTRAIT: (1080, 1920),
}


def normalize_aspect_ratio(aspect_ratio: str | None) -> str:
    """Return a supported aspect ratio, preserving landscape as the legacy default."""
    if aspect_ratio == PORTRAIT:
        return PORTRAIT
    return LANDSCAPE


def resolution_for_aspect_ratio(aspect_ratio: str | None) -> tuple[int, int]:
    return VIDEO_RESOLUTIONS[normalize_aspect_ratio(aspect_ratio)]
