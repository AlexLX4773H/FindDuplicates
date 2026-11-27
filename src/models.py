"""
Core Data Models
Defines structured classes for manga chapters, doujinshi works, duplicate groups,
partial issues, and file operations.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class DuplicateCategory(str, Enum):
    EXACT_DUPLICATE = "exact_duplicate"
    ALTERNATIVE_SCANLATION = "alternative_scanlation"
    FRACTIONAL_SPLIT = "fractional_split"
    VERSION_UPGRADE = "version_upgrade"
    CROSS_DIRECTORY = "cross_directory"
    PAGE_MISMATCH = "page_mismatch"
    VISUAL_MATCH = "visual_match"


class ActionType(str, Enum):
    KEEP = "keep"
    MOVE_ARCHIVE = "move_archive"
    DELETE = "delete"
    SKIP = "skip"


@dataclass
class ChapterItem:
    raw_name: str
    series_name: str
    chapter_num: Optional[float]
    chapter_raw: str
    volume_num: Optional[float] = None
    scanlator_group: Optional[str] = None
    hash_id: Optional[str] = None  # e.g., Mangadex hash '48a245'
    is_partial: bool = False
    is_special: bool = False
    is_fixed: bool = False  # e.g., '_fixed_'
    is_hq: bool = False     # e.g., 'HQ version'
    is_version_upgrade: bool = False # e.g., 'v2'
    page_count: int = 0
    file_size_bytes: int = 0
    file_path: str = ""
    is_archive: bool = False
    status_category: str = ""
    volume_root: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_name": self.raw_name,
            "series_name": self.series_name,
            "chapter_num": self.chapter_num,
            "chapter_raw": self.chapter_raw,
            "volume_num": self.volume_num,
            "scanlator_group": self.scanlator_group,
            "hash_id": self.hash_id,
            "is_partial": self.is_partial,
            "is_special": self.is_special,
            "is_fixed": self.is_fixed,
            "is_hq": self.is_hq,
            "is_version_upgrade": self.is_version_upgrade,
            "page_count": self.page_count,
            "file_size_bytes": self.file_size_bytes,
            "file_path": self.file_path,
            "is_archive": self.is_archive,
            "status_category": self.status_category,
            "volume_root": self.volume_root,
        }


@dataclass
class DoujinshiWork:
    raw_name: str
    work_name: str
    clean_title: str
    secondary_title: Optional[str] = None
    artist: Optional[str] = None
    circle: Optional[str] = None
    event: Optional[str] = None
    language: Optional[str] = None
    scanlator: Optional[str] = None
    is_decensored: bool = False
    is_digital: bool = False
    is_complete: bool = False
    is_anthology: bool = False
    page_count: int = 0
    file_size_bytes: int = 0
    file_path: str = ""
    is_archive: bool = False
    source_root: str = ""
    inner_chapter_folder: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_name": self.raw_name,
            "work_name": self.work_name,
            "clean_title": self.clean_title,
            "secondary_title": self.secondary_title,
            "artist": self.artist,
            "circle": self.circle,
            "event": self.event,
            "language": self.language,
            "scanlator": self.scanlator,
            "is_decensored": self.is_decensored,
            "is_digital": self.is_digital,
            "is_complete": self.is_complete,
            "is_anthology": self.is_anthology,
            "page_count": self.page_count,
            "file_size_bytes": self.file_size_bytes,
            "file_path": self.file_path,
            "is_archive": self.is_archive,
            "source_root": self.source_root,
            "inner_chapter_folder": self.inner_chapter_folder,
        }


@dataclass
class DuplicateGroup:
    group_id: str
    target_type: str  # 'manga' or 'doujinshi'
    title: str
    sub_title: str  # e.g., 'Chapter 1.0' or 'Circle (Artist)'
    category: DuplicateCategory
    items: List[Dict[str, Any]]
    recommendation: str
    recommended_keep_path: str
    hamming_distance: Optional[int] = None
    position_matched: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "target_type": self.target_type,
            "title": self.title,
            "sub_title": self.sub_title,
            "category": self.category.value if isinstance(self.category, DuplicateCategory) else str(self.category),
            "items": self.items,
            "recommendation": self.recommendation,
            "recommended_keep_path": self.recommended_keep_path,
            "hamming_distance": self.hamming_distance,
            "position_matched": self.position_matched,
        }


@dataclass
class PartialIssue:
    issue_id: str
    series_name: str
    issue_type: str  # 'fractional_overlap', 'low_page_count', 'keyword_flagged', 'missing_chapters'
    description: str
    affected_items: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "series_name": self.series_name,
            "issue_type": self.issue_type,
            "description": self.description,
            "affected_items": self.affected_items,
        }


@dataclass
class FileActionPlan:
    item_path: str
    action: ActionType
    destination_path: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_path": self.item_path,
            "action": self.action.value,
            "destination_path": self.destination_path,
            "reason": self.reason,
        }
