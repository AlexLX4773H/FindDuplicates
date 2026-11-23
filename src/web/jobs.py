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

from src.config import load_config


class ScanJobCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, description="User-defined friendly name for the scan job")
    target_type: str = Field("manga", description="'manga', 'doujinshi', or 'all'")
    paths: List[str] = Field(..., min_items=1, description="One or more target directory paths to scan")
    mode: str = Field("name", description="'name' or 'image'")
    description: Optional[str] = ""


class ScanJobUpdatePayload(BaseModel):
    name: Optional[str] = None
    target_type: Optional[str] = None
    paths: Optional[List[str]] = None
    mode: Optional[str] = None
    description: Optional[str] = None


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

        job_slug = re.sub(r"[^a-zA-Z0-9]+", "_", payload.name.strip().lower()).strip("_")
        unique_id = f"job_{job_slug}_{uuid.uuid4().hex[:6]}"

        new_job = {
            "id": unique_id,
            "name": payload.name.strip(),
            "target_type": payload.target_type.strip().lower(),
            "paths": clean_paths,
            "mode": payload.mode.strip().lower(),
            "description": payload.description.strip() if payload.description else "",
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
        if payload.description is not None:
            target_job["description"] = payload.description.strip()

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
