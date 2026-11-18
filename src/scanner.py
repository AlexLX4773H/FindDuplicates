"""
Filesystem and Archive Scanner
Recursively walks user directories, parses chapter metadata, and counts pages
without decompressing full archives.
"""

import os
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Generator
from src.parser import ChapterInfo, extract_chapter_number, extract_group, is_marked_partial, is_marked_special, clean_series_name

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp"}
ARCHIVE_EXTENSIONS = {".cbz", ".zip"}

def count_pages_in_folder(folder_path: Path) -> int:
    """Counts valid image files inside a chapter directory."""
    count = 0
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_file() and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                    count += 1
    except (PermissionError, OSError):
        pass
    return count

def count_pages_in_archive(archive_path: Path) -> int:
    """Counts valid image files inside a .zip or .cbz archive from header."""
    count = 0
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            for name in z.namelist():
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS and not name.startswith('__MACOSX'):
                    count += 1
    except (zipfile.BadZipFile, OSError, PermissionError):
        pass
    return count

def scan_manga_directory(root_path: Path) -> List[ChapterInfo]:
    """
    Scans a root manga directory where immediate subdirectories are series titles:
    root_path / <Series Name> / <Chapter 01 or Chapter 01.cbz>
    """
    results: List[ChapterInfo] = []
    if not root_path.exists():
        return results

    try:
        for series_dir in root_path.iterdir():
            if not series_dir.is_dir():
                continue

            raw_series = series_dir.name
            normalized_series = clean_series_name(raw_series)

            # Look for chapters inside the series directory
            for item in series_dir.iterdir():
                is_archive = item.is_file() and item.suffix.lower() in ARCHIVE_EXTENSIONS
                is_folder = item.is_dir()

                if not (is_archive or is_folder):
                    continue

                ch_num = extract_chapter_number(item.stem if is_archive else item.name)
                group = extract_group(item.stem if is_archive else item.name)
                partial = is_marked_partial(item.name)
                special = is_marked_special(item.name)

                # Count pages for comparison
                pages = count_pages_in_archive(item) if is_archive else count_pages_in_folder(item)

                info = ChapterInfo(
                    raw_name=item.name,
                    series_name=normalized_series,
                    chapter_num=ch_num,
                    chapter_raw=item.stem if is_archive else item.name,
                    scanlator_group=group,
                    is_partial=partial,
                    is_special=special,
                    page_count=pages,
                    file_path=str(item),
                    is_archive=is_archive
                )
                results.append(info)

    except (PermissionError, OSError) as e:
        print(f"[Warning] Access issue scanning {root_path}: {e}")

    return results
