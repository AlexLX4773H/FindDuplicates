"""
Duplicate & Partial Chapter Detection Engine
Applies tailored duplicate detection algorithms:
- Manga: Intra-series grouping (chapter numbers, scanlator variations, fractional overlaps).
- Doujinshi: Global cross-directory matching (artist + title normalization, tag preferences).
"""

import uuid
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional
from src.models import ChapterItem, DoujinshiWork, DuplicateGroup, DuplicateCategory, PartialIssue


# ==============================================================================
# Manga Detection Engine (Intra-Series Scope)
# ==============================================================================

def detect_manga_duplicates(chapters: List[ChapterItem]) -> List[DuplicateGroup]:
    """
    Finds duplicate chapters strictly within each manga/manhwa series.
    """
    # Group by (normalized_series_name, chapter_num)
    grouped: Dict[Tuple[str, float], List[ChapterItem]] = defaultdict(list)
    for ch in chapters:
        if ch.chapter_num is not None:
            grouped[(ch.series_name.lower(), ch.chapter_num)].append(ch)

    duplicate_groups: List[DuplicateGroup] = []

    for (series_key, ch_num), items in grouped.items():
        if len(items) > 1:
            series_display = items[0].series_name or series_key
            groups_seen = set(ch.scanlator_group for ch in items if ch.scanlator_group)
            has_fixed = any(ch.is_fixed for ch in items)
            has_hq = any(ch.is_hq for ch in items)
            has_v2 = any(ch.is_version_upgrade for ch in items)

            # Determine category and recommended keeper
            if has_fixed or has_hq or has_v2:
                category = DuplicateCategory.VERSION_UPGRADE
                # Choose the fixed / HQ / v2 version
                keeper = next((ch for ch in items if ch.is_fixed or ch.is_hq or ch.is_version_upgrade), items[0])
                rec = f"Version upgrade detected. Keep '{keeper.raw_name}' and archive earlier release."
            elif len(groups_seen) > 1:
                category = DuplicateCategory.ALTERNATIVE_SCANLATION
                # Prefer one with highest page count or larger file size
                keeper = max(items, key=lambda c: (c.page_count, c.file_size_bytes))
                rec = f"Multiple scanlation groups found ({', '.join(groups_seen)}). Review translation quality."
            else:
                category = DuplicateCategory.EXACT_DUPLICATE
                keeper = items[0]
                rec = "Identical chapter number found. Safe to keep one and archive duplicates."

            duplicate_groups.append(
                DuplicateGroup(
                    group_id=f"manga_{uuid.uuid4().hex[:8]}",
                    target_type="manga",
                    title=series_display,
                    sub_title=f"Chapter {ch_num:g}",
                    category=category,
                    items=[c.to_dict() for c in items],
                    recommendation=rec,
                    recommended_keep_path=keeper.file_path or keeper.raw_name
                )
            )

    return duplicate_groups


def detect_manga_partials(chapters: List[ChapterItem], min_page_ratio: float = 0.60) -> List[PartialIssue]:
    """
    Identifies partial or fragmented chapters within each manga:
    1. Fractional sub-chapters (e.g. 10.1, 10.2) coexisting with full chapter (10.0).
    2. Chapters flagged with incomplete/sample keywords.
    3. Chapters with suspiciously low page counts compared to peer releases.
    """
    issues: List[PartialIssue] = []
    series_map: Dict[str, List[ChapterItem]] = defaultdict(list)
    for ch in chapters:
        series_map[ch.series_name.lower()].append(ch)

    for series_key, items in series_map.items():
        series_display = items[0].series_name or series_key

        # 1. Keyword flagged
        for ch in items:
            if ch.is_partial:
                issues.append(
                    PartialIssue(
                        issue_id=f"part_{uuid.uuid4().hex[:8]}",
                        series_name=series_display,
                        issue_type="keyword_flagged",
                        description=f"Chapter '{ch.raw_name}' is flagged as incomplete/sample.",
                        affected_items=[ch.to_dict()]
                    )
                )

        # 2. Fractional sub-chapters coexisting with full chapter
        num_to_ch: Dict[float, List[ChapterItem]] = defaultdict(list)
        for ch in items:
            if ch.chapter_num is not None:
                num_to_ch[ch.chapter_num].append(ch)

        integers_present = set(int(n) for n in num_to_ch.keys() if n.is_integer())
        decimals_present = set(n for n in num_to_ch.keys() if not n.is_integer())

        for dec in decimals_present:
            parent_int = int(dec)
            if parent_int in integers_present:
                full_chapters = num_to_ch.get(float(parent_int), [])
                fractional_chapters = num_to_ch.get(dec, [])
                issues.append(
                    PartialIssue(
                        issue_id=f"part_{uuid.uuid4().hex[:8]}",
                        series_name=series_display,
                        issue_type="fractional_overlap",
                        description=f"Sub-chapter {dec:g} coexists with consolidated Chapter {parent_int}.",
                        affected_items=[c.to_dict() for c in (full_chapters + fractional_chapters)]
                    )
                )

        # 3. Low page count ratio compared to duplicate releases
        for ch_num, ch_list in num_to_ch.items():
            if len(ch_list) > 1:
                max_pages = max(c.page_count for c in ch_list)
                if max_pages >= 10:
                    for c in ch_list:
                        if c.page_count > 0 and (c.page_count / max_pages) < min_page_ratio:
                            issues.append(
                                PartialIssue(
                                    issue_id=f"part_{uuid.uuid4().hex[:8]}",
                                    series_name=series_display,
                                    issue_type="low_page_count",
                                    description=(
                                        f"Chapter '{c.raw_name}' has only {c.page_count} pages, "
                                        f"while companion release has {max_pages} pages."
                                    ),
                                    affected_items=[c.to_dict()]
                                )
                            )

    return issues


# ==============================================================================
# Doujinshi Detection Engine (Global Cross-Directory Scope)
# ==============================================================================

def detect_doujinshi_duplicates(works: List[DoujinshiWork]) -> List[DuplicateGroup]:
    """
    Finds duplicate doujinshi works across the entire library.
    Matches primarily by (Artist, Title) and secondarily by Title for non-generic names.
    """
    GENERIC_WORDS = {"chapter", "vol", "readthechapter", "completed", "done", "files", "folder", "newfolder"}

    by_key: Dict[Tuple[str, str], List[DoujinshiWork]] = defaultdict(list)

    for w in works:
        if not w.clean_title or len(w.clean_title) < 4:
            continue
        art_key = w.artist.lower().replace(" ", "") if w.artist else ""
        
        # If artist is present, group by (artist, title)
        if art_key:
            by_key[(art_key, w.clean_title)].append(w)
            if w.secondary_title and len(w.secondary_title) >= 4:
                by_key[(art_key, w.secondary_title)].append(w)
        else:
            # Only match uncredited artist if title is distinctive (not generic)
            if len(w.clean_title) >= 6 and not any(w.clean_title.startswith(g) for g in GENERIC_WORDS):
                by_key[("", w.clean_title)].append(w)
                if w.secondary_title and len(w.secondary_title) >= 6 and not any(w.secondary_title.startswith(g) for g in GENERIC_WORDS):
                    by_key[("", w.secondary_title)].append(w)

    duplicate_groups: List[DuplicateGroup] = []
    seen_work_paths = set()

    for (art_key, title_key), items in by_key.items():
        # Ensure we have distinct file/folder paths (not duplicate references)
        unique_paths = set(w.file_path for w in items)
        if len(unique_paths) > 1:
            # Check if this group was already processed
            path_key = tuple(sorted(unique_paths))
            if path_key in seen_work_paths:
                continue
            seen_work_paths.add(path_key)

            first = items[0]
            display_title = first.work_name
            artist_display = first.artist or (f"Circle: {first.circle}" if first.circle else "Uncredited Artist")

            # Determine best copy to keep:
            # 1. Prefer Decensored
            # 2. Prefer Complete
            # 3. Prefer Digital
            # 4. Prefer highest page count / largest file size
            def rank_work(w: DoujinshiWork):
                score = 0
                if w.is_decensored:
                    score += 100
                if w.is_complete:
                    score += 50
                if w.is_digital:
                    score += 25
                score += (w.page_count * 2)
                score += (w.file_size_bytes // 1_000_000)
                return score

            best_keeper = max(items, key=rank_work)

            reasons = []
            if best_keeper.is_decensored:
                reasons.append("Decensored")
            if best_keeper.is_digital:
                reasons.append("Digital")
            if best_keeper.is_complete:
                reasons.append("Complete")
            reason_str = f" ({', '.join(reasons)})" if reasons else ""

            rec = (
                f"Identical work found in multiple locations. "
                f"Recommend keeping '{best_keeper.work_name}'{reason_str} and archiving duplicates."
            )

            duplicate_groups.append(
                DuplicateGroup(
                    group_id=f"doujin_{uuid.uuid4().hex[:8]}",
                    target_type="doujinshi",
                    title=display_title,
                    sub_title=artist_display,
                    category=DuplicateCategory.CROSS_DIRECTORY,
                    items=[w.to_dict() for w in items],
                    recommendation=rec,
                    recommended_keep_path=best_keeper.file_path or best_keeper.raw_name
                )
            )

    return duplicate_groups
