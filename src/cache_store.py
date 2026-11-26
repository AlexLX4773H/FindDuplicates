"""
On-disk cache used by expensive scans.
Video fingerprints live under cache/video_fingerprints/.
Clearing removes files inside the cache directory and leaves reports and jobs alone.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import load_config


def resolve_cache_directory(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Absolute cache root from config, defaulting to ./cache."""
    if cfg is None:
        cfg = load_config()
    raw = (cfg.get("image_inspection") or {}).get("cache_directory") or "./cache"
    return Path(raw).resolve()


def video_fingerprint_dir(cache_dir: Optional[Path] = None) -> Path:
    root = cache_dir if cache_dir is not None else resolve_cache_directory()
    return Path(root) / "video_fingerprints"


def cache_summary(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    """File count and byte size of everything under the cache directory."""
    root = Path(cache_dir) if cache_dir is not None else resolve_cache_directory()
    file_count = 0
    size_bytes = 0
    if root.exists():
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                file_count += 1
                try:
                    size_bytes += (Path(dirpath) / name).stat().st_size
                except OSError:
                    continue
    return {
        "path": str(root),
        "exists": root.exists(),
        "file_count": file_count,
        "size_bytes": size_bytes,
    }


def clear_cache(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Delete files and subfolders inside the cache directory.
    The cache directory itself is kept. Paths outside it are never touched.
    """
    root = Path(cache_dir) if cache_dir is not None else resolve_cache_directory()
    root = root.resolve()
    deleted_files = 0
    freed_bytes = 0
    if root.exists():
        for child in list(root.iterdir()):
            try:
                if child.is_file() or child.is_symlink():
                    freed_bytes += child.stat().st_size
                    child.unlink()
                    deleted_files += 1
                elif child.is_dir():
                    for dirpath, _dirnames, filenames in os.walk(child):
                        for name in filenames:
                            fp = Path(dirpath) / name
                            try:
                                freed_bytes += fp.stat().st_size
                                deleted_files += 1
                            except OSError:
                                deleted_files += 1
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                continue
    root.mkdir(parents=True, exist_ok=True)
    summary = cache_summary(root)
    summary["deleted_files"] = deleted_files
    summary["freed_bytes"] = freed_bytes
    return summary
