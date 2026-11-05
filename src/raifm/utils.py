"""
Helper utils.
"""

import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    """get file sha256 hash"""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def hash_gen(paths: list[Path]) -> dict[Path, str]:
    """get all sha256 hash for file in list"""
    return {path: sha256(path) for path in paths}
