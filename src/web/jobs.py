"""
Scan Jobs Management Module
Handles persistent storage, retrieval, and execution configuration of reusable scan jobs.
Supports multiple directory locations, custom library target types (Manga/Manhwa, Doujinshi, All),
and detection modalities.
"""

import os
import json
import uuid
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.config import load_config, normalize_path


class ScanJobCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, description="User-defined friendly name for the scan job")
    target_type: str = Field("manga", description="'manga', 'doujinshi', 'video', or 'all'")
    paths: List[str] = Field(..., min_items=1, description="Compare directories. For a reference job these are the folders to clean.")
    mode: str = Field("name", description="'name', 'image', 'visual', 'exact', 'reference', or 'similar'")
    description: Optional[str] = ""
    excluded_manga: Optional[List[str]] = Field(default_factory=list, description="Manga series names/titles to exclude from scan")
    reference_paths: Optional[List[str]] = Field(default_factory=list, description="Canonical directories used to decide which exact copy to keep")


class ScanJobUpdatePayload(BaseModel):
    name: Optional[str] = None
    target_type: Optional[str] = None
    paths: Optional[List[str]] = None
    mode: Optional[str] = None
    description: Optional[str] = None
    excluded_manga: Optional[List[str]] = None
    reference_paths: Optional[List[str]] = None


def _clean_path_list(paths: Optional[List[str]]) -> List[str]:
    return [p.strip() for p in (paths or []) if p and str(p).strip()]


def _path_key(raw: str) -> str:
    try:
        resolved = str(normalize_path(raw))
    except Exception:
        resolved = raw.strip()
    return os.path.normcase(os.path.normpath(resolved))


def _path_contains(parent_key: str, child_key: str) -> bool:
    if parent_key == child_key:
        return True
    prefix = parent_key.rstrip("\\/") + os.sep
    return child_key.startswith(prefix)


def normalize_job_mode(target_type: str, mode: str) -> tuple:
    """
    Video jobs always use similar-frame matching.
    Similar mode is not valid for manga or doujinshi.
    """
    target = (target_type or "").strip().lower()
    selected = (mode or "").strip().lower()
    if target == "video":
        return target, "similar"
    if selected == "similar":
        raise ValueError("Similar video mode is only available for the Videos library.")
    return target, selected


def validate_reference_directories(
    target_type: str,
    mode: str,
    paths: Optional[List[str]],
    reference_paths: Optional[List[str]],
) -> List[str]:
    """
    Reference jobs are doujinshi-only and need two disjoint directory lists.
    Other modes keep any stored reference paths without extra requirements.
    """
    cleaned_refs = _clean_path_list(reference_paths)
    if (mode or "").strip().lower() != "reference":
        return cleaned_refs

    cleaned_paths = _clean_path_list(paths)
    if (target_type or "").strip().lower() != "doujinshi":
        raise ValueError("Reference jobs are only available for Doujinshi libraries.")
    if not cleaned_paths:
        raise ValueError("At least one compare directory is required.")
    if not cleaned_refs:
        raise ValueError("At least one reference directory is required.")

    compare_keys = [_path_key(p) for p in cleaned_paths]
    ref_keys = [_path_key(p) for p in cleaned_refs]
    for left in compare_keys:
        for right in ref_keys:
            if _path_contains(left, right) or _path_contains(right, left):
                raise ValueError("Compare directories and reference directories must not overlap.")
    return cleaned_refs


class ScanJobManager:
    """Manages persistent scan jobs stored in JSON on disk."""

    def __init__(self, filename: str = "scan_jobs.json"):
        self.filename = filename

    def _get_storage_path(self) -> Path:
        """Resolves persistent storage path inside reports directory or workspace."""
        try:
            cfg = load_config()
            rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
            rep_dir.mkdir(parents=True, exist_ok=True)
            return rep_dir / self.filename
        except Exception:
            return Path(self.filename).resolve()

    def _get_default_jobs(self) -> List[Dict[str, Any]]:
        """Returns standard initial jobs based on system configuration."""
        cfg = load_config()
        manga_defaults = [str(p) for p in cfg.get("manga_paths", ["/sg2b/Share2sgb/Manga"])]
        doujin_defaults = [str(p) for p in cfg.get("doujinshi_paths", ["/media/devmon/L500/Vere NewFolder"])]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return [
            {
                "id": "job_default_manga",
                "name": "Default Manga / Manhwa Library",
                "target_type": "manga",
                "paths": manga_defaults,
                "mode": "name",
                "description": "Standard intra-series scan across primary Manga & Manhwa directories",
                "excluded_manga": [],
                "created_at": now,
                "last_run": None,
                "last_status": "never_run",
                "last_report_file": None,
                "last_duplicates_count": 0
            },
            {
                "id": "job_default_doujinshi",
                "name": "Default Doujinshi Library",
                "target_type": "doujinshi",
                "paths": doujin_defaults,
                "mode": "name",
                "description": "Standard cross-directory deduplication across primary Doujinshi collections",
                "excluded_manga": [],
                "created_at": now,
                "last_run": None,
                "last_status": "never_run",
                "last_report_file": None,
                "last_duplicates_count": 0
            }
        ]

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Reads and returns all saved scan jobs."""
        path = self._get_storage_path()
        if not path.exists():
            defaults = self._get_default_jobs()
            self._save_all(defaults)
            return defaults

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            print(f"[Warning] Failed to read scan jobs from {path}: {e}")
            return self._get_default_jobs()

    def _save_all(self, jobs: List[Dict[str, Any]]) -> None:
        """Writes jobs list to JSON storage."""
        path = self._get_storage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single job by ID."""
        jobs = self.list_jobs()
        for j in jobs:
            if j.get("id") == job_id:
                return j
        return None

    def create_job(self, payload: ScanJobCreatePayload) -> Dict[str, Any]:
        """Creates and persists a new user-defined scan job."""
        jobs = self.list_jobs()
        clean_paths = [p.strip() for p in payload.paths if p.strip()]
        if not clean_paths:
            raise ValueError("At least one valid scan directory path is required.")

        target_type, mode = normalize_job_mode(payload.target_type, payload.mode)
        clean_refs = validate_reference_directories(target_type, mode, clean_paths, payload.reference_paths)

        job_slug = re.sub(r"[^a-zA-Z0-9]+", "_", payload.name.strip().lower()).strip("_")
        unique_id = f"job_{job_slug}_{uuid.uuid4().hex[:6]}"

        clean_exclusions = [ex.strip() for ex in (payload.excluded_manga or []) if ex.strip()]

        new_job = {
            "id": unique_id,
            "name": payload.name.strip(),
            "target_type": target_type,
            "paths": clean_paths,
            "mode": mode,
            "description": payload.description.strip() if payload.description else "",
            "excluded_manga": clean_exclusions,
            "reference_paths": clean_refs,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_run": None,
            "last_status": "never_run",
            "last_report_file": None,
            "last_duplicates_count": 0
        }

        jobs.append(new_job)
        self._save_all(jobs)
        return new_job

    def update_job(self, job_id: str, payload: ScanJobUpdatePayload) -> Optional[Dict[str, Any]]:
        """Updates an existing scan job's configuration."""
        jobs = self.list_jobs()
        target_job = None
        for j in jobs:
            if j.get("id") == job_id:
                target_job = j
                break

        if not target_job:
            return None

        if payload.name is not None and payload.name.strip():
            target_job["name"] = payload.name.strip()
        if payload.target_type is not None and payload.target_type.strip():
            target_job["target_type"] = payload.target_type.strip().lower()
        if payload.paths is not None:
            clean = [p.strip() for p in payload.paths if p.strip()]
            if clean:
                target_job["paths"] = clean
        if payload.mode is not None and payload.mode.strip():
            target_job["mode"] = payload.mode.strip().lower()
        target_job["target_type"], target_job["mode"] = normalize_job_mode(
            target_job.get("target_type", ""),
            target_job.get("mode", ""),
        )
        if payload.description is not None:
            target_job["description"] = payload.description.strip()
        if payload.excluded_manga is not None:
            target_job["excluded_manga"] = [ex.strip() for ex in payload.excluded_manga if ex.strip()]
        if payload.reference_paths is not None:
            target_job["reference_paths"] = _clean_path_list(payload.reference_paths)

        target_job["reference_paths"] = validate_reference_directories(
            target_job.get("target_type", ""),
            target_job.get("mode", ""),
            target_job.get("paths"),
            target_job.get("reference_paths"),
        )

        self._save_all(jobs)
        return target_job

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job by ID."""
        jobs = self.list_jobs()
        initial_len = len(jobs)
        filtered = [j for j in jobs if j.get("id") != job_id]
        if len(filtered) < initial_len:
            self._save_all(filtered)
            return True
        return False

    def update_job_run_status(self, job_id: str, status: str, report_file: Optional[str] = None, duplicates_count: int = 0) -> None:
        """Updates the run status and last report for a job."""
        jobs = self.list_jobs()
        for j in jobs:
            if j.get("id") == job_id:
                j["last_status"] = status
                j["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if report_file:
                    j["last_report_file"] = report_file
                j["last_duplicates_count"] = duplicates_count
                break
        self._save_all(jobs)


# Global singleton instance
job_manager = ScanJobManager()
