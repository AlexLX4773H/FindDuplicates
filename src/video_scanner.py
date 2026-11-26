"""
Walk an arbitrary directory tree and collect video files.
No folder layout is assumed. mp4 and mkv are the expected bulk.
"""

import os
from pathlib import Path
from typing import Callable, List, Optional

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".m4v", ".webm", ".avi", ".mov"}


def is_video_file(name: str) -> bool:
    return Path(name).suffix.lower() in VIDEO_EXTENSIONS and not Path(name).name.startswith("._")


def scan_video_tree(root: Path, progress_callback: Optional[Callable] = None) -> List[dict]:
    """
    Recursively collect video files under root.
    Each item carries the path, size, and mtime used as the fingerprint cache key.
    """
    root = Path(root)
    found: List[dict] = []
    if not root.exists():
        return found

    if progress_callback:
        progress_callback(f"Walking video tree: '{root}'...", "SCAN")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"} and not d.startswith(".")]
        for name in filenames:
            if not is_video_file(name):
                continue
            path = Path(dirpath) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            found.append({
                "raw_name": name,
                "file_path": str(path),
                "file_size_bytes": stat.st_size,
                "mtime": stat.st_mtime,
                "source_root": str(root),
            })

    if progress_callback:
        progress_callback(f"Found {len(found)} video files under '{root.name or root}'.", "INFO")
    return found
