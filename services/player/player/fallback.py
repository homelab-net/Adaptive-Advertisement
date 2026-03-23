"""
Fallback bundle — the on-device asset rendered when no approved manifest is active.

The fallback bundle is:
- Validated at startup before any other service dependency is checked.
- Always present on-device; it must never require a network fetch.
- Displayed in FALLBACK state (startup, connection loss) and SAFE_MODE.

Never-blank invariant starts here: if validate() fails, main.py aborts before
any display driver is initialised, preventing a blank/black screen boot.

Supported asset types and extensions
--------------------------------------
image : .jpg, .jpeg, .png
video : .mp4, .webm
html  : .html

For the MVP the default fallback is a single static image (fallback.jpg).
A more elaborate loop can be substituted by changing FALLBACK_ASSET_NAME.
"""
import logging
from pathlib import Path
from typing import Optional

from . import config

log = logging.getLogger(__name__)

_EXT_TO_TYPE: dict[str, str] = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".mp4": "video",
    ".webm": "video",
    ".html": "html",
}


class FallbackBundleMissingError(RuntimeError):
    """Raised when the fallback asset cannot be located or is unsupported."""


class FallbackBundle:
    """
    Encapsulates the fallback asset path and type.
    Call validate() once at startup; then asset_path and asset_type are safe to use.
    """

    def __init__(self) -> None:
        self._asset_path: Optional[str] = None
        self._asset_type: Optional[str] = None

    def validate(self) -> None:
        """
        Confirm that the configured fallback asset exists and has a supported type.
        Raises FallbackBundleMissingError if either check fails.
        This must be the first thing main() does.
        """
        bundle_dir = Path(config.FALLBACK_BUNDLE_PATH)
        asset_path = bundle_dir / config.FALLBACK_ASSET_NAME

        if not asset_path.exists():
            raise FallbackBundleMissingError(
                f"Fallback asset not found: {asset_path}\n"
                "Place a supported asset file at this path before starting the player.\n"
                f"Supported extensions: {list(_EXT_TO_TYPE.keys())}"
            )

        ext = asset_path.suffix.lower()
        asset_type = _EXT_TO_TYPE.get(ext)
        if asset_type is None:
            raise FallbackBundleMissingError(
                f"Fallback asset has unsupported extension '{ext}': {asset_path}\n"
                f"Supported extensions: {list(_EXT_TO_TYPE.keys())}"
            )

        self._asset_path = str(asset_path)
        self._asset_type = asset_type
        log.info(
            "fallback bundle validated: path=%s type=%s", self._asset_path, self._asset_type
        )

    @property
    def asset_path(self) -> str:
        if self._asset_path is None:
            raise FallbackBundleMissingError("validate() has not been called.")
        return self._asset_path

    @property
    def asset_type(self) -> str:
        if self._asset_type is None:
            raise FallbackBundleMissingError("validate() has not been called.")
        return self._asset_type
