"""
Duplicate & Partial Chapter Detection Logic
Analyzes parsed chapter lists to identify exact duplicates, scanlator variations,
partial/fractional chapters, and incomplete releases.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any
from src.parser import ChapterInfo

@dataclass
class DuplicateGroup:
    series_name: str
    chapter_num: float
    chapters: List[ChapterInfo]
    category: str  # 'exact_duplicate', 'alternative_scanlation', 'cross_directory'
    recommendation: str

@dataclass
class PartialIssue:
    series_name: str
    issue_type: str  # 'fractional_chapter', 'low_page_count', 'keyword_flagged'
    description: str
    affected_chapters: List[ChapterInfo]

def detect_duplicates(chapters: List[ChapterInfo]) -> List[DuplicateGroup]:
    """
    Groups chapters by series and chapter number to find duplicates.
    """
    # Group by (normalized_series, chapter_num)
    grouped: Dict[Tuple[str, float], List[ChapterInfo]] = defaultdict(list)
    for ch in chapters:
        if ch.chapter_num is not None:
            grouped[(ch.series_name.lower(), ch.chapter_num)].append(ch)

    duplicate_groups: List[DuplicateGroup] = []

    for (series_key, ch_num), items in grouped.items():
        if len(items) > 1:
            series_display = items[0].series_name
            # Check if scanlators differ
            groups_seen = set(ch.scanlator_group for ch in items if ch.scanlator_group)
            pages_set = set(ch.page_count for ch in items if ch.page_count > 0)

            if len(groups_seen) > 1:
                category = "alternative_scanlation"
                rec = "Multiple scanlation teams found. Review quality, translation, and page count."
            elif len(pages_set) <= 1:
                category = "exact_duplicate"
                rec = "Identical chapter files found across paths. Safe to prune duplicate."
            else:
                category = "page_mismatch_duplicate"
                rec = "Duplicate chapter number with differing page counts. Review before deleting."

            duplicate_groups.append(
                DuplicateGroup(
                    series_name=series_display,
                    chapter_num=ch_num,
                    chapters=items,
                    category=category,
                    recommendation=rec
                )
            )

    return duplicate_groups

def detect_partials(chapters: List[ChapterInfo], min_page_ratio: float = 0.60) -> List[PartialIssue]:
    """
    Identifies partial or incomplete chapters:
    1. Fractional sub-chapters (e.g. 10.1, 10.2) when full chapter (10) exists or vice-versa.
    2. Chapters with page counts significantly lower than counterpart releases.
    3. Chapters flagged with keywords ([Incomplete], [Sample], etc.).
    """
    issues: List[PartialIssue] = []

    # Group by series
    series_map: Dict[str, List[ChapterInfo]] = defaultdict(list)
    for ch in chapters:
        series_map[ch.series_name.lower()].append(ch)

    for series_key, items in series_map.items():
        series_display = items[0].series_name

        # 1. Check for keyword flags
        for ch in items:
            if ch.is_partial:
                issues.append(
                    PartialIssue(
                        series_name=series_display,
                        issue_type="keyword_flagged",
                        description=f"Chapter '{ch.raw_name}' contains an incomplete/sample indicator in filename.",
                        affected_chapters=[ch]
                    )
                )

        # 2. Check for fractional vs integer chapters (e.g. 10.1, 10.2 vs 10.0)
        nums = [ch.chapter_num for ch in items if ch.chapter_num is not None]
        num_to_ch = defaultdict(list)
        for ch in items:
            if ch.chapter_num is not None:
                num_to_ch[ch.chapter_num].append(ch)

        integers_present = set(int(n) for n in nums if n.is_integer())
        decimals_present = set(n for n in nums if not n.is_integer())

        for dec in decimals_present:
            parent_int = int(dec)
            if parent_int in integers_present:
                # Both full chapter and fractional sub-chapter exist
                full_chapters = num_to_ch.get(float(parent_int), [])
                fractional_chapters = num_to_ch.get(dec, [])
                issues.append(
                    PartialIssue(
                        series_name=series_display,
                        issue_type="fractional_overlap",
                        description=f"Sub-chapter {dec} coexists with consolidated Chapter {parent_int}.",
                        affected_chapters=full_chapters + fractional_chapters
                    )
                )

        # 3. Check for suspiciously low page count compared to duplicate or peer releases
        # Group by chapter_num
        for ch_num, ch_list in num_to_ch.items():
            if len(ch_list) > 1:
                max_pages = max(c.page_count for c in ch_list)
                if max_pages >= 10:  # Only if reasonable length
                    for c in ch_list:
                        if c.page_count > 0 and (c.page_count / max_pages) < min_page_ratio:
                            issues.append(
                                PartialIssue(
                                    series_name=series_display,
                                    issue_type="low_page_count",
                                    description=(
                                        f"Chapter '{c.raw_name}' has only {c.page_count} pages, "
                                        f"while companion release has {max_pages} pages."
                                    ),
                                    affected_chapters=[c]
                                )
                            )

    return issues
