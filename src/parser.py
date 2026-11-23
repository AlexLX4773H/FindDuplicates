"""
Naming Parser & Heuristic Tokenizer
Extracts structured metadata from folder and archive names for Manga, Manhwa, and Doujinshi.
Also parses raw text directory trees (Windows tree /a and tree /f exports).
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from src.models import ChapterItem, DoujinshiWork

# Regex patterns for chapter extraction
CHAPTER_PATTERNS = [
    # "Vol. 1 Ch. 12.5", "Vol. 2 Ch. 10"
    re.compile(r'(?:vol\.?\s*\d+\s+)?(?:chapter|ch\.?|c)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # "Episode 12", "Ep. 12"
    re.compile(r'(?:episode|ep\.?)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # Standalone number like "#12", "#01"
    re.compile(r'#\s*(\d+(?:\.\d+)?)'),
    # Trailing chapter number at the end of string: "Title - 012"
    re.compile(r'[-_]\s*(\d+(?:\.\d+)?)\s*(?:\[|\(|$)', re.IGNORECASE),
]

VOLUME_PATTERN = re.compile(r'vol\.?\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
HEX_HASH_PATTERN = re.compile(r'_([0-9a-f]{6})$', re.IGNORECASE)

PARTIAL_KEYWORDS = ["incomplete", "sample", "preview", "partial", "missing", "tbr"]
SPECIAL_KEYWORDS = ["omake", "extra", "prologue", "epilogue", "special", "side story", "oneshot"]
LEAF_CHAPTER_NAMES = {"chapter", "_chapter", "read the chapter"}


# ==============================================================================
# Manga / Manhwa Parsers
# ==============================================================================

def strip_hex_hash(text: str) -> Tuple[str, Optional[str]]:
    """Strips download scraper 6-character hex hash like '_48a245'."""
    m = HEX_HASH_PATTERN.search(text)
    if m:
        cleaned = text[:m.start()].strip()
        return cleaned, m.group(1).lower()
    return text, None


def extract_group(text: str) -> Optional[str]:
    """
    Extracts scanlation group from either:
    1. Leading brackets: [Group Name] Title
    2. Underscore prefix before chapter indicator: Fuyuking_Ch.1... or RE_SCANS OF KWEGOSAURUS_Ch.5...
    """
    # 1. Bracketed group
    m_bracket = re.match(r'^\s*\[([^\]]+)\]', text)
    if m_bracket:
        return m_bracket.group(1).strip()

    # 2. Underscore separator before chapter/vol: "Scanlator_Ch. 1"
    m_under = re.match(r'^([^_]+)_(?:Vol\.\s*\d+\s+)?(?:Ch\.|Chapter|c\d)', text, re.IGNORECASE)
    if m_under:
        group_raw = m_under.group(1).strip()
        # Ensure it's not a volume indicator like 'Vol. 1'
        if not re.match(r'^vol\.?\s*\d+$', group_raw, re.IGNORECASE):
            return group_raw

    return None


def extract_chapter_number(name: str) -> Optional[float]:
    """Extracts numeric chapter value (handles floats for sub-chapters e.g., 20.1)."""
    # Strip hex hash first so it doesn't confuse numbers
    cleaned, _ = strip_hex_hash(name)
    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def extract_volume_number(name: str) -> Optional[float]:
    """Extracts volume number if present e.g., 'Vol. 1 Ch. 12'."""
    m = VOLUME_PATTERN.search(name)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def is_marked_partial(name: str) -> bool:
    """Checks if the chapter contains keywords indicating incomplete release."""
    lowered = name.lower()
    return any(kw in lowered for kw in PARTIAL_KEYWORDS)


def is_marked_special(name: str) -> bool:
    """Checks if the item is an omake, prologue, or special."""
    lowered = name.lower()
    return any(kw in lowered for kw in SPECIAL_KEYWORDS)


def is_marked_fixed(name: str) -> bool:
    """Checks for fixed or v2 tags."""
    lowered = name.lower()
    return "_fixed_" in lowered or "[fixed]" in lowered or "[v2]" in lowered or " v2" in lowered


def is_marked_hq(name: str) -> bool:
    """Checks for high quality tags."""
    lowered = name.lower()
    return "hq version" in lowered or "[hq]" in lowered or "(hq)" in lowered


def clean_series_name(name: str) -> str:
    """Removes bracketed groups, resolution tags, and formatting."""
    cleaned = re.sub(r'\[[^\]]*\]', '', name)
    cleaned = re.sub(r'\([^\)]*\)', '', cleaned)
    cleaned = re.sub(r'[_.-]', ' ', cleaned)
    return " ".join(cleaned.split()).strip()


def parse_manga_chapter_name(raw_name: str, series_name: str = "", file_path: str = "") -> ChapterItem:
    """Creates a structured ChapterItem from a folder or archive name."""
    cleaned_name, hash_id = strip_hex_hash(raw_name)
    ch_num = extract_chapter_number(cleaned_name)
    vol_num = extract_volume_number(cleaned_name)
    group = extract_group(raw_name)
    is_part = is_marked_partial(raw_name)
    is_spec = is_marked_special(raw_name)
    is_fix = is_marked_fixed(raw_name)
    is_high_q = is_marked_hq(raw_name)
    is_v2 = "[v2]" in raw_name.lower() or " v2" in raw_name.lower()

    return ChapterItem(
        raw_name=raw_name,
        series_name=clean_series_name(series_name) if series_name else "",
        chapter_num=ch_num,
        chapter_raw=cleaned_name,
        volume_num=vol_num,
        scanlator_group=group,
        hash_id=hash_id,
        is_partial=is_part,
        is_special=is_spec,
        is_fixed=is_fix,
        is_hq=is_high_q,
        is_version_upgrade=is_v2,
        file_path=file_path,
        is_archive=file_path.lower().endswith(('.cbz', '.zip', '.cbr', '.rar'))
    )


# ==============================================================================
# Doujinshi / H Parsers
# ==============================================================================

EVENT_PATTERN = re.compile(r'^\s*\((C\d+|COMIC1[^\)]*|SC\d+|FF\d+|AC\d+|M3[^\)]*)\)', re.IGNORECASE)
CIRCLE_ARTIST_PATTERN = re.compile(r'^\s*\[(?P<circle>[^\(\]]+?)(?:\s*\((?P<artist>[^\)]+)\))?\]')


def is_leaf_chapter_folder(folder_name: str) -> bool:
    """Determines whether a directory is a child chapter folder rather than the main work."""
    lowered = folder_name.lower().strip()
    if lowered in LEAF_CHAPTER_NAMES:
        return True
    if lowered.endswith('_chapter') or lowered.endswith('_chapter_tmp'):
        return True
    if re.match(r'^(?:chapter|ch\.?|vol\.?)\s*\d+', lowered):
        return True
    if re.match(r'^\d+(\.\d+)?\s*[-_]', lowered):
        return True
    return False


def parse_doujinshi_name(raw_name: str, file_path: str = "") -> DoujinshiWork:
    """
    Parses complex doujinshi title conventions:
    (Event) [Circle (Artist)] Title (Parody) [Language] [Scanlator] [Tags]
    """
    rem = raw_name.strip()

    # 1. Event extraction: (C96), (COMIC1☆10)
    event = None
    ev_m = EVENT_PATTERN.match(rem)
    if ev_m:
        event = ev_m.group(1).strip()
        rem = rem[ev_m.end():].strip()

    # 2. Circle & Artist: [Circle (Artist)] or [Artist]
    circle = None
    artist = None
    art_m = CIRCLE_ARTIST_PATTERN.match(rem)
    if art_m:
        circle_candidate = art_m.group('circle').strip()
        artist_candidate = art_m.group('artist')
        if artist_candidate:
            circle = circle_candidate
            artist = artist_candidate.strip()
        else:
            artist = circle_candidate
        rem = rem[art_m.end():].strip()

    # 3. Detect tags before stripping
    lowered = raw_name.lower()
    is_decensored = "decensored" in lowered
    is_digital = "digital" in lowered
    is_complete = "complete" in lowered

    # Extract language if present
    language = "English" if "[english]" in lowered or "(english)" in lowered else None

    # Scanlator group: check trailing brackets
    scanlator = None
    trailing_brackets = re.findall(r'\[([^\]]+)\]', rem)
    for b in reversed(trailing_brackets):
        b_low = b.lower()
        if b_low not in {"english", "decensored", "digital", "complete", "hq"} and not b_low.startswith("c"):
            scanlator = b.strip()
            break

    # 4. Clean Title
    clean_title = re.sub(r'\[[^\]]*\]', '', rem)
    clean_title = re.sub(r'\{[^\}]*\}', '', clean_title)
    clean_title = re.sub(r'\([^\)]*\)', '', clean_title)

    # Check for dual-title pattern: Japanese Title _ English Title
    secondary_title = None
    if ' _ ' in clean_title or ' ~ ' in clean_title:
        parts = re.split(r'\s*[_~]\s*', clean_title)
        if len(parts) >= 2 and len(parts[0].strip()) > 2 and len(parts[1].strip()) > 2:
            clean_title = parts[0].strip()
            secondary_title = parts[1].strip()

    # Final alphanumeric normalization for robust matching
    norm_main = re.sub(r'[^a-zA-Z0-9]', '', clean_title).lower()
    norm_sec = re.sub(r'[^a-zA-Z0-9]', '', secondary_title).lower() if secondary_title else None

    return DoujinshiWork(
        raw_name=raw_name,
        work_name=raw_name,
        clean_title=norm_main,
        secondary_title=norm_sec,
        artist=artist,
        circle=circle,
        event=event,
        language=language,
        scanlator=scanlator,
        is_decensored=is_decensored,
        is_digital=is_digital,
        is_complete=is_complete,
        file_path=file_path,
        is_archive=file_path.lower().endswith(('.zip', '.cbz', '.rar', '.cbr'))
    )


# ==============================================================================
# Raw Tree Dump Ingestion
# ==============================================================================

def parse_tree_dump_lines(lines: List[str], excluded_manga: Optional[List[str]] = None) -> Tuple[str, List[Any]]:
    """
    Parses Windows 'tree /a' or 'tree /f' output lines.
    Automatically detects whether the tree is a Manga 4-level structure or Doujinshi tree.
    Returns: ('manga' | 'doujinshi', parsed_items_list)
    """
    stack: List[str] = []
    nodes: List[List[str]] = []
    excluded_set = {ex.strip().lower() for ex in (excluded_manga or []) if ex.strip()}

    for line in lines:
        m = re.match(r'^(\s*(?:[|\xa6]\s*)*)\+---(.*)', line)
        if m:
            prefix, name = m.group(1), m.group(2).strip()
            depth = len(prefix) // 3
            stack = stack[:depth]
            stack.append(name)
            nodes.append(list(stack))

    if not nodes:
        return ("unknown", [])

    # Identify whether this is Manga structure (Volume -> Category -> Series -> Chapter)
    # Check top nodes for known Manga volume keywords or 4-level depth dominance
    sample_top = set(n[0] for n in nodes[:50])
    is_manga = any(k in " ".join(sample_top).lower() for k in ["manga", "manhwa", "webtoon"])

    if is_manga:
        chapter_items: List[ChapterItem] = []
        for path_parts in nodes:
            # Depth 3 is the chapter level: [Volume, Status, Series, Chapter]
            if len(path_parts) >= 4:
                vol_root = path_parts[0]
                status_cat = path_parts[1]
                series_name = path_parts[2]
                chapter_name = path_parts[3]

                if excluded_set:
                    clean = clean_series_name(series_name).lower()
                    s_lower = series_name.lower()
                    if any(ex in s_lower or ex == clean for ex in excluded_set):
                        continue

                item = parse_manga_chapter_name(chapter_name, series_name, "/".join(path_parts))
                item.volume_root = vol_root
                item.status_category = status_cat
                chapter_items.append(item)
        return ("manga", chapter_items)

    else:
        # Doujinshi structure: collapse child leaf folders
        parents = set(tuple(n[:-1]) for n in nodes if len(n) > 1)
        doujin_works: List[DoujinshiWork] = []

        for path_parts in nodes:
            t = tuple(path_parts)
            # We want leaf nodes or nodes whose children are just 'Chapter' / '_Chapter'
            is_leaf = t not in parents
            if is_leaf:
                last_name = path_parts[-1]
                if is_leaf_chapter_folder(last_name) and len(path_parts) > 1:
                    work_name = path_parts[-2]
                    work_path = "/".join(path_parts[:-1])
                    inner_ch = last_name
                else:
                    work_name = last_name
                    work_path = "/".join(path_parts)
                    inner_ch = None

                # Ignore pure digits or top bucket names
                if len(work_name) > 3 and not work_name.isdigit():
                    work = parse_doujinshi_name(work_name, work_path)
                    work.inner_chapter_folder = inner_ch
                    work.source_root = path_parts[0] if path_parts else ""
                    doujin_works.append(work)

        return ("doujinshi", doujin_works)
