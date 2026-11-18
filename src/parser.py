"""
Naming Parser & Heuristic Tokenizer
Extracts manga title, chapter numbers (integers & decimals),
scanlation groups, and partial status flags from folder or archive names.
"""

import re
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ChapterInfo:
    raw_name: str
    series_name: str
    chapter_num: Optional[float]
    chapter_raw: str
    scanlator_group: Optional[str] = None
    is_partial: bool = False
    is_special: bool = False  # e.g., omake, extra, prologue
    page_count: int = 0
    file_path: str = ""
    is_archive: bool = False

# Regex patterns for chapter extraction
CHAPTER_PATTERNS = [
    # "Ch. 12.5", "Chapter 12", "c012", "ch 01"
    re.compile(r'(?:chapter|ch\.?|c)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # "Episode 12", "Ep. 12"
    re.compile(r'(?:episode|ep\.?)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # Standalone number like "#12", "#01"
    re.compile(r'#\s*(\d+(?:\.\d+)?)'),
    # Trailing chapter number at the end of string: "Title - 012"
    re.compile(r'[-_]\s*(\d+(?:\.\d+)?)\s*(?:\[|\(|$)', re.IGNORECASE),
]

PARTIAL_KEYWORDS = ["incomplete", "sample", "preview", "partial", "missing", "tbr"]
SPECIAL_KEYWORDS = ["omake", "extra", "prologue", "epilogue", "special", "side story", "oneshot"]

def extract_group(text: str) -> Optional[str]:
    """Extracts scanlation group from leading brackets e.g. [Group Name]"""
    match = re.match(r'^\s*\[([^\]]+)\]', text)
    if match:
        return match.group(1).strip()
    return None

def extract_chapter_number(name: str) -> Optional[float]:
    """Extracts numeric chapter value (including decimals for sub-chapters)."""
    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(name)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None

def is_marked_partial(name: str) -> bool:
    """Checks if the chapter contains keywords indicating incomplete release."""
    lowered = name.lower()
    return any(kw in lowered for kw in PARTIAL_KEYWORDS)

def is_marked_special(name: str) -> bool:
    """Checks if the item is an omake, prologue, or special."""
    lowered = name.lower()
    return any(kw in lowered for kw in SPECIAL_KEYWORDS)

def clean_series_name(name: str) -> str:
    """Removes bracketed groups, resolution tags, and formatting."""
    cleaned = re.sub(r'\[[^\]]*\]', '', name)
    cleaned = re.sub(r'\([^\)]*\)', '', cleaned)
    cleaned = re.sub(r'[_.-]', ' ', cleaned)
    return " ".join(cleaned.split()).strip()
