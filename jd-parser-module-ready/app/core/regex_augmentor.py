"""Re-export regex augmentation symbols from app.core.chunker for backward compatibility."""

from app.core.chunker import (
    extract_common_metadata,
    regex_augment,
)

__all__ = ["extract_common_metadata", "regex_augment"]
