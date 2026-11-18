"""
Filesystem and Archive Scanner
Recursively walks user directories, parses chapter metadata, and counts pages
without decompressing full archives.
"""

import os
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple
from src.models import ChapterItem, DoujinshiWork
from src.parser import (
    parse_manga_chapter_name,
    parse_doujinshi_name,
    is_leaf_chapter_folder,
    clean_series_name
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip"}


def count_pages_in_folder(folder_path: Path) -> Tuple[int, int]:
    """Counts valid image files inside a chapter directory and total bytes."""
    count = 0
    total_size = 0
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_file() and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                    count += 1
                    try:
                        total_size += entry.stat().st_size
                    except OSError:
                        pass
    except (PermissionError, OSError):
        pass
    return count, total_size


def count_pages_in_archive(archive_path: Path) -> Tuple[int, int]:
    """Counts valid image files inside a .zip or .cbz archive from header and total archive bytes."""
    count = 0
    total_size = 0
    try:
        total_size = archive_path.stat().st_size
    except OSError:
        pass

    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            for name in z.namelist():
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS and not name.startswith('__MACOSX'):
                    count += 1
    except (zipfile.BadZipFile, OSError, PermissionError):
        pass
    return count, total_size


def scan_manga_directory(root_path: Path) -> List[ChapterItem]:
    """
    Scans a manga directory structure.
    Adapts automatically to either:
    1. Multi-level: Root / Status_Bucket / Series / Chapter
    2. Standard: Root / Series / Chapter
    """
    results: List[ChapterItem] = []
    if not root_path.exists():
        return results

    try:
        # Check subdirectories
        for entry in root_path.iterdir():
            if not entry.is_dir():
                continue

            # Check if this subdirectory is a status category or directly a series
            # Look at children to test depth
            has_nested_series = False
            for sub in entry.iterdir():
                if sub.is_dir() and any(c.is_dir() or c.suffix.lower() in ARCHIVE_EXTENSIONS for c in sub.iterdir()):
                    has_nested_series = True
                    break

            if has_nested_series:
                # Hierarchy: root_path / status_category / series_name / chapter
                status_cat = entry.name
                for series_dir in entry.iterdir():
                    if not series_dir.is_dir():
                        continue
                    series_name = series_dir.name
                    for item in series_dir.iterdir():
                        is_arch = item.is_file() and item.suffix.lower() in ARCHIVE_EXTENSIONS
                        is_fold = item.is_dir()
                        if not (is_arch or is_fold):
                            continue

                        pages, size = count_pages_in_archive(item) if is_arch else count_pages_in_folder(item)
                        ch = parse_manga_chapter_name(item.name, series_name, str(item))
                        ch.status_category = status_cat
                        ch.volume_root = root_path.name
                        ch.page_count = pages
                        ch.file_size_bytes = size
                        results.append(ch)
            else:
                # Standard hierarchy: root_path / series_name / chapter
                series_name = entry.name
                for item in entry.iterdir():
                    is_arch = item.is_file() and item.suffix.lower() in ARCHIVE_EXTENSIONS
                    is_fold = item.is_dir()
                    if not (is_arch or is_fold):
                        continue

                    pages, size = count_pages_in_archive(item) if is_arch else count_pages_in_folder(item)
                    ch = parse_manga_chapter_name(item.name, series_name, str(item))
                    ch.volume_root = root_path.name
                    ch.page_count = pages
                    ch.file_size_bytes = size
                    results.append(ch)

    except (PermissionError, OSError) as e:
        print(f"[Warning] Access issue scanning {root_path}: {e}")

    return results


def scan_doujinshi_directory(root_path: Path) -> List[DoujinshiWork]:
    """
    Recursively scans a doujinshi / H root directory.
    Identifies standalone works, archives, and multi-chapter series.
    Collapses leaf '_chapter' directories into their parent works.
    """
    works: List[DoujinshiWork] = []
    if not root_path.exists():
        return works

    try:
        for current_root, dirs, files in os.walk(root_path):
            current_path = Path(current_root)

            # Check archive files in this folder
            for f in files:
                f_path = current_path / f
                if f_path.suffix.lower() in ARCHIVE_EXTENSIONS:
                    pages, size = count_pages_in_archive(f_path)
                    dw = parse_doujinshi_name(f_path.stem, str(f_path))
                    dw.is_archive = True
                    dw.page_count = pages
                    dw.file_size_bytes = size
                    dw.source_root = root_path.name
                    works.append(dw)

            # Check folders representing works
            # If a folder has images or only has child folder like '_chapter', treat it as a work
            if current_path != root_path:
                name = current_path.name
                if not is_leaf_chapter_folder(name) and len(name) > 3 and not name.isdigit():
                    # Check if images exist here or inside child chapter folder
                    pages, size = count_pages_in_folder(current_path)
                    child_chapter = None
                    if pages == 0:
                        # Check subdirectories for chapter folders
                        for d in dirs:
                            if is_leaf_chapter_folder(d):
                                sub_p, sub_s = count_pages_in_folder(current_path / d)
                                if sub_p > 0:
                                    pages = sub_p
                                    size = sub_s
                                    child_chapter = d
                                    break

                    if pages > 0:
                        dw = parse_doujinshi_name(name, str(current_path))
                        dw.page_count = pages
                        dw.file_size_bytes = size
                        dw.source_root = root_path.name
                        dw.inner_chapter_folder = child_chapter
                        works.append(dw)

    except (PermissionError, OSError) as e:
        print(f"[Warning] Access issue scanning {root_path}: {e}")

    return works
