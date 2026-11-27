"""
Interactive Web Application & API Server
FastAPI backend powering the interactive dashboard inside Docker & CasaOS.
Provides endpoints to trigger scans, configure multiple scan paths, review duplicates,
and click-to-confirm file actions.
"""

import os
import re
import threading
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import load_config, normalize_path
from src.detector import (
    detect_manga_duplicates,
    detect_manga_partials,
    detect_missing_chapters,
    detect_doujinshi_duplicates,
    detect_visual_duplicates,
    detect_exact_hash_duplicates,
    detect_reference_duplicates,
    detect_video_duplicates,
    retain_visual_matches,
)
from src.scanner import scan_manga_directory, scan_doujinshi_directory
from src.video_scanner import scan_video_tree
from src.cache_store import cache_summary, clear_cache
from src.parser import parse_tree_dump_lines
from src.actions import ActionExecutor
from src.reporter import export_json, export_csv, export_html
from src.models import DuplicateGroup, PartialIssue
from src.web.jobs import job_manager, ScanJobCreatePayload, ScanJobUpdatePayload, normalize_job_mode, validate_reference_directories

app = FastAPI(title="FindDuplicates Dashboard", version="2.1.0")

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
if _ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

# In-memory session state for interactive UI
STATE = {
    "is_scanning": False,
    "last_scan_time": None,
    "total_scanned": 0,
    "manga_duplicates": [],  # List[DuplicateGroup]
    "manga_partials": [],    # List[PartialIssue]
    "doujinshi_duplicates": [], # List[DuplicateGroup]
    "video_duplicates": [],     # List[DuplicateGroup]
    "status_message": "Ready. No active scan running.",
    "scan_progress": "",
    "logs": [],              # List[Dict[str, Any]]
    "active_scan_info": None, # Optional[Dict[str, Any]]
    "loaded_report_name": None,
    "run_history": [],       # List[Dict[str, Any]]
    "queue": [],             # Waiting scan entries
    "running_entry": None,   # Scan entry currently executing
}

class ScanCancelled(Exception):
    """Raised when the user cancels the scan that is in progress."""


_SCAN_LOCK = threading.Lock()
_CANCEL = threading.Event()
_SCAN_THREAD_ID: Optional[int] = None

_REPORT_META_CACHE: Dict[str, Any] = {}
_HIDDEN_REPORTS = {"scan_jobs.json", "latest_report.json"}


def _skip_report_file(name: str) -> bool:
    return name in _HIDDEN_REPORTS


def _cached_report_meta(path: Path) -> Dict[str, Any]:
    """Parse a report JSON once per path, size, and mtime."""
    import json
    stat = path.stat()
    token = (getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)), stat.st_size)
    key = str(path.resolve())
    cached = _REPORT_META_CACHE.get(key)
    if cached and cached[0] == token:
        return cached[1]

    meta = {
        "duplicates_count": 0,
        "partials_count": 0,
        "total_scanned": 0,
        "job_name": None,
        "job_id": None,
        "created_at": None,
        "target": None,
        "mode": None,
    }
    try:
        with open(path, "r", encoding="utf-8") as jf:
            jdata = json.load(jf)
        dupes = jdata.get("duplicates", [])
        parts = jdata.get("partials", [])
        file_meta = jdata.get("metadata") or {}
        summary = jdata.get("summary") or {}
        meta["duplicates_count"] = len(dupes) if isinstance(dupes, list) else 0
        meta["partials_count"] = len(parts) if isinstance(parts, list) else 0
        meta["total_scanned"] = summary.get("total_scanned", meta["duplicates_count"])
        meta["job_name"] = file_meta.get("job_name")
        meta["job_id"] = file_meta.get("job_id")
        meta["created_at"] = file_meta.get("created_at") or jdata.get("generated_at")
        meta["target"] = file_meta.get("target")
        meta["mode"] = file_meta.get("mode")
    except Exception:
        pass
    _REPORT_META_CACHE[key] = (token, meta)
    return meta

_LOG_ID_COUNTER = 0

def add_scan_log(message: str, level: str = "INFO"):
    """Appends a timestamped log entry to STATE with level tags.

    PROGRESS updates the live subtitle only, so a long hash can show the
    current folder without adding a log row for every item.
    A raised cancel flag stops the scan at this log line.
    """
    if _CANCEL.is_set() and threading.get_ident() == _SCAN_THREAD_ID:
        raise ScanCancelled()
    normalized = (level or "INFO").upper()
    STATE["scan_progress"] = message
    if normalized == "PROGRESS":
        return
    global _LOG_ID_COUNTER
    _LOG_ID_COUNTER += 1
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "id": _LOG_ID_COUNTER,
        "time": timestamp,
        "level": normalized,  # INFO, SCAN, HASH, WARN, ERROR, SUCCESS
        "message": message
    }
    STATE["logs"].append(entry)
    if len(STATE["logs"]) > 1000:
        STATE["logs"] = STATE["logs"][-1000:]
    print(f"[{timestamp}] [{normalized}] {message}")


def record_run_history(target: str, mode: str, total_scanned: int, duplicates_count: int, partials_count: int, duration_sec: float, report_file: str, status: str = "completed", job_name: Optional[str] = None, job_id: Optional[str] = None):
    """Records completed scan runs in persistent history."""
    entry = {
        "id": f"run_{len(STATE['run_history']) + 1}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": target,
        "mode": mode,
        "job_name": job_name or f"{target.capitalize()} Scan",
        "job_id": job_id,
        "total_scanned": total_scanned,
        "duplicates_count": duplicates_count,
        "partials_count": partials_count,
        "duration_seconds": duration_sec,
        "report_file": report_file,
        "status": status
    }
    STATE["run_history"].insert(0, entry)
    if len(STATE["run_history"]) > 50:
        STATE["run_history"] = STATE["run_history"][:50]


def _init_run_history_from_reports():
    """Initializes run history entries from saved report files on disk."""
    import json
    try:
        cfg = load_config()
        rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
        if not rep_dir.exists():
            return
        for idx, f in enumerate(sorted(rep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True), 1):
            if _skip_report_file(f.name):
                continue
            try:
                meta = _cached_report_meta(f)
                job_name = meta.get("job_name")
                target = meta.get("target") or ("manga" if "manga" in f.name.lower() else "doujinshi")
                mode = meta.get("mode") or "name"
                timestamp = meta.get("created_at")
                if not timestamp:
                    timestamp = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    timestamp = str(timestamp).replace("T", " ")[:19]

                if not job_name:
                    if "manga" in f.name.lower():
                        job_name = "Manga / Manhwa Scan"
                    elif "h_new_b2" in f.name.lower():
                        job_name = "Offline Tree Dump (h_new_b2)"
                    elif "h_temp_d" in f.name.lower():
                        job_name = "Offline Tree Dump (h_temp_d)"
                    elif "doujin" in f.name.lower():
                        job_name = "Doujinshi Scan"
                    else:
                        job_name = "Saved Scan Report"

                STATE["run_history"].append({
                    "id": f"run_hist_{idx}",
                    "timestamp": timestamp,
                    "target": target,
                    "mode": mode,
                    "job_name": job_name,
                    "job_id": meta.get("job_id"),
                    "total_scanned": meta.get("total_scanned", 0),
                    "duplicates_count": meta.get("duplicates_count", 0),
                    "partials_count": meta.get("partials_count", 0),
                    "duration_seconds": 1.5,
                    "report_file": f.name,
                    "status": "completed"
                })
            except Exception:
                pass
    except Exception:
        pass

job_manager.mark_stale_running_jobs()
_init_run_history_from_reports()

action_executor = ActionExecutor(default_archive_dir="./archive")


class ActionItemPayload(BaseModel):
    item_path: str
    action: str  # 'keep', 'move_archive', 'delete', 'skip'
    reason: Optional[str] = ""


class ExecuteActionsPayload(BaseModel):
    dry_run: bool = True
    custom_archive_dir: Optional[str] = None
    actions: List[ActionItemPayload]


class ParseTreePayload(BaseModel):
    file_path: str
    tree_type: Optional[str] = "auto"  # 'auto', 'manga', 'doujinshi'


class ScanPayload(BaseModel):
    target: str = "manga"  # 'manga', 'doujinshi', 'video', 'all'
    mode: str = "name"     # 'name', 'image', 'visual', 'exact', 'reference', 'missing', 'similar'
    paths: Optional[List[str]] = None
    manga_paths: Optional[List[str]] = None
    doujinshi_paths: Optional[List[str]] = None
    reference_paths: Optional[List[str]] = None
    job_id: Optional[str] = None
    job_name: Optional[str] = None
    excluded_manga: Optional[List[str]] = None
    queue: bool = False


class QueueReorderPayload(BaseModel):
    queue_id: str
    direction: str


def _public_queue_entry(entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not entry:
        return None
    return {
        "queue_id": entry.get("queue_id"),
        "job_id": entry.get("job_id"),
        "job_name": entry.get("job_name") or "Scan",
        "target": entry.get("target"),
        "mode": entry.get("mode"),
    }


def _new_scan_entry(
    job_name: str,
    target: str,
    mode: str,
    paths: Optional[List[str]],
    reference_paths: Optional[List[str]],
    excluded_manga: Optional[List[str]],
    job_id: Optional[str] = None,
    manga_paths: Optional[List[str]] = None,
    doujinshi_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "queue_id": f"q_{uuid.uuid4().hex[:8]}",
        "job_id": job_id,
        "job_name": job_name,
        "target": target,
        "mode": mode,
        "paths": list(paths or []),
        "manga_paths": manga_paths,
        "doujinshi_paths": doujinshi_paths,
        "reference_paths": list(reference_paths or []),
        "excluded_manga": list(excluded_manga or []),
    }


def _submit_scan(entry: Dict[str, Any], background_tasks: BackgroundTasks, queue: bool) -> str:
    """Start the entry now, append it, or report that a scan is already running."""
    with _SCAN_LOCK:
        if STATE["is_scanning"]:
            if not queue:
                return "busy"
            STATE["queue"].append(entry)
            return "queued"
        STATE["is_scanning"] = True
        STATE["running_entry"] = entry
    _begin_scan(entry["target"], entry["mode"], entry.get("job_id"), entry.get("job_name"), entry["queue_id"])
    if entry.get("job_id"):
        job_manager.update_job_run_status(entry["job_id"], status="running")
    background_tasks.add_task(_scan_driver)
    return "started"


def _scan_driver() -> None:
    """Run the current entry, then each queued entry, until the queue is empty."""
    global _SCAN_THREAD_ID
    _SCAN_THREAD_ID = threading.get_ident()
    try:
        while True:
            with _SCAN_LOCK:
                entry = dict(STATE["running_entry"]) if STATE.get("running_entry") else None
            if not entry:
                with _SCAN_LOCK:
                    STATE["is_scanning"] = False
                return
            _CANCEL.clear()
            if entry.get("job_id"):
                job_manager.update_job_run_status(entry["job_id"], status="running")
            try:
                _run_background_scan(
                    target=entry["target"],
                    mode=entry["mode"],
                    paths=entry.get("paths"),
                    manga_paths=entry.get("manga_paths"),
                    doujinshi_paths=entry.get("doujinshi_paths"),
                    job_id=entry.get("job_id"),
                    job_name=entry.get("job_name"),
                    excluded_manga=entry.get("excluded_manga"),
                    reference_paths=entry.get("reference_paths"),
                    queue_id=entry.get("queue_id"),
                )
            except ScanCancelled:
                _CANCEL.clear()
                if entry.get("job_id"):
                    job_manager.update_job_run_status(entry["job_id"], status="cancelled")
                add_scan_log(f"Scan cancelled: '{entry.get('job_name') or 'Scan'}'.", "WARN")
                STATE["status_message"] = "Scan cancelled."
                STATE["scan_progress"] = "Scan cancelled."
                if STATE.get("active_scan_info"):
                    STATE["active_scan_info"]["status"] = "cancelled"
                    STATE["active_scan_info"]["queue_id"] = entry.get("queue_id")
            with _SCAN_LOCK:
                if STATE["queue"]:
                    STATE["running_entry"] = STATE["queue"].pop(0)
                    continue
                STATE["running_entry"] = None
                STATE["is_scanning"] = False
                return
    finally:
        if _SCAN_THREAD_ID == threading.get_ident():
            _SCAN_THREAD_ID = None


@app.get("/api/state")
def get_state():
    """Returns the current state and duplicate statistics."""
    return {
        "is_scanning": STATE["is_scanning"],
        "last_scan_time": STATE["last_scan_time"],
        "total_scanned": STATE["total_scanned"],
        "status_message": STATE["status_message"],
        "scan_progress": STATE["scan_progress"],
        "manga_duplicates_count": len(STATE["manga_duplicates"]),
        "manga_partials_count": len(STATE["manga_partials"]),
        "doujinshi_duplicates_count": len(STATE["doujinshi_duplicates"]),
        "video_duplicates_count": len(STATE.get("video_duplicates", [])),
        "active_scan_info": STATE.get("active_scan_info"),
        "loaded_report_name": STATE.get("loaded_report_name") or None,
        "run_history_count": len(STATE.get("run_history", [])),
        "running": _public_queue_entry(STATE.get("running_entry")) if STATE.get("is_scanning") else None,
        "queue": [_public_queue_entry(entry) for entry in STATE.get("queue", [])],
    }


@app.get("/api/logs")
def get_logs(since_id: int = 0, limit: int = 300):
    """Returns incremental or recent scan log entries."""
    if since_id > 0:
        new_logs = [entry for entry in STATE["logs"] if entry["id"] > since_id]
        logs_to_return = new_logs[:limit]
    else:
        logs_to_return = STATE["logs"][-limit:]

    return {
        "is_scanning": STATE["is_scanning"],
        "scan_progress": STATE["scan_progress"],
        "status_message": STATE["status_message"],
        "active_scan_info": STATE.get("active_scan_info"),
        "logs": logs_to_return,
        "last_id": STATE["logs"][-1]["id"] if STATE["logs"] else 0,
        "total_logs": len(STATE["logs"])
    }


@app.post("/api/logs/clear")
def clear_logs():
    """Clears the live log output buffer."""
    STATE["logs"].clear()
    return {"status": "cleared"}


@app.get("/api/config-paths")
def get_config_paths():
    """Returns configured and detected paths for Manga and Doujinshi."""
    cfg = load_config()
    return {
        "manga_defaults": [
            "/sg2b/Share2sgb/Manga"
        ],
        "doujinshi_defaults": [
            "/media/devmon/L500/Vere NewFolder"
        ],
        "current_scan_paths": [str(p) for p in cfg.get("normalized_scan_paths", [])],
        "archive_dir": os.getenv("ARCHIVE_DIR", "./archive"),
        "reports_dir": os.getenv("OUTPUT_DIR", "./reports"),
    }


@app.get("/api/casaos-compose")
def get_casaos_compose():
    """Returns the pre-configured docker-compose.casaos.yml content for 1-click CasaOS import."""
    for name in ["docker-compose.casaos.yml", "docker-compose.yml"]:
        p = Path(name)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return {"content": f.read()}
    return {"content": "# docker compose file not found"}


@app.get("/api/reports")
def list_reports():
    """Lists saved reports with metadata, duplicate counts, origin job, creation time, and available export formats."""
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    reports = []
    if rep_dir.exists():
        for f in sorted(rep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if _skip_report_file(f.name):
                continue

            meta = _cached_report_meta(f)
            dupes_count = meta.get("duplicates_count", 0)
            partials_count = meta.get("partials_count", 0)
            scanned_count = meta.get("total_scanned", dupes_count)
            job_name = meta.get("job_name")
            job_id = meta.get("job_id")
            created_at = meta.get("created_at")

            # Fallback for job_name if not in report metadata
            if not job_name:
                for r in STATE.get("run_history", []):
                    if r.get("report_file") == f.name and r.get("job_name"):
                        job_name = r.get("job_name")
                        break
            if not job_name:
                fname_lower = f.name.lower()
                if "manga" in fname_lower:
                    job_name = "Manga / Manhwa Scan"
                elif "h_new_b2" in fname_lower:
                    job_name = "Offline Tree Dump (h_new_b2)"
                elif "h_temp_d" in fname_lower:
                    job_name = "Offline Tree Dump (h_temp_d)"
                elif "doujin" in fname_lower:
                    job_name = "Doujinshi Scan"
                else:
                    job_name = "Manual Deduplication Scan"

            if not created_at:
                created_at = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at = str(created_at).replace("T", " ")[:19]

            stem = f.stem
            html_file = rep_dir / f"{stem}.html"
            csv_file = rep_dir / f"{stem}.csv"

            reports.append({
                "filename": f.name,
                "stem": stem,
                "path": str(f),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "created_at": created_at,
                "job_name": job_name,
                "job_id": job_id,
                "size_bytes": f.stat().st_size,
                "duplicates_count": dupes_count,
                "partials_count": partials_count,
                "total_scanned": scanned_count,
                "has_html": html_file.exists(),
                "html_filename": html_file.name if html_file.exists() else None,
                "has_csv": csv_file.exists(),
                "csv_filename": csv_file.name if csv_file.exists() else None,
                "is_active": (f.name == STATE.get("loaded_report_name"))
            })

    return {
        "reports": reports,
        "loaded_report_name": STATE.get("loaded_report_name"),
        "run_history": STATE.get("run_history", [])
    }


@app.get("/api/run-history")
def get_run_history():
    """Returns past scan execution runs and active report info."""
    return {
        "run_history": STATE.get("run_history", []),
        "loaded_report_name": STATE.get("loaded_report_name") or None
    }


@app.get("/api/reports/download/{filename}")
def download_report(filename: str):
    """Serves report files (HTML, CSV, JSON) for viewing or downloading in browser."""
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    target = (rep_dir / filename).resolve()
    # Security check: must reside inside rep_dir
    if not str(target).startswith(str(rep_dir)) or not target.exists():
        return JSONResponse(status_code=404, content={"error": f"Report file not found: {filename}"})

    media_type = "application/octet-stream"
    suffix = target.suffix.lower()
    if suffix == ".html":
        media_type = "text/html; charset=utf-8"
    elif suffix == ".csv":
        media_type = "text/csv; charset=utf-8"
    elif suffix == ".json":
        media_type = "application/json; charset=utf-8"

    return FileResponse(target, media_type=media_type, filename=target.name)


class DeleteReportPayload(BaseModel):
    filename: str


def _execute_report_deletion(filename: str):
    """Safely removes a report JSON file and its sibling HTML/CSV export files."""
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    target = (rep_dir / filename).resolve()

    if not str(target).startswith(str(rep_dir)):
        return JSONResponse(status_code=403, content={"error": "Access denied: Invalid file path"})

    deleted_files = []
    if target.exists() and target.is_file():
        try:
            target.unlink()
            deleted_files.append(target.name)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to delete {filename}: {e}"})

    # Also clean up sibling export files (.html, .csv, .json) with the same stem
    stem = target.stem
    for ext in [".html", ".csv", ".json"]:
        sibling = rep_dir / f"{stem}{ext}"
        if sibling.exists() and sibling.is_file() and sibling.name not in deleted_files:
            try:
                sibling.unlink()
                deleted_files.append(sibling.name)
            except Exception:
                pass

    if not deleted_files:
        return JSONResponse(status_code=404, content={"error": f"Report not found: {filename}"})

    # If the deleted report was active in memory, clear the active resolution window
    if STATE.get("loaded_report_name") in (filename, f"{stem}.json", f"{stem}.html", f"{stem}.csv"):
        STATE["loaded_report_name"] = None
        STATE["manga_duplicates"] = []
        STATE["doujinshi_duplicates"] = []
        STATE["video_duplicates"] = []
        STATE["manga_partials"] = []
        STATE["total_scanned"] = 0
        STATE["status_message"] = f"Report '{filename}' removed. Resolution window cleared."

    # Update run history
    STATE["run_history"] = [
        r for r in STATE.get("run_history", [])
        if r.get("report_file") not in (filename, f"{stem}.json", f"{stem}.html", f"{stem}.csv")
    ]

    add_scan_log(f"Permanently removed report '{filename}' ({len(deleted_files)} files removed: {', '.join(deleted_files)})", "INFO")
    return {"status": "deleted", "filename": filename, "deleted_files": deleted_files}


@app.delete("/api/reports/{filename}")
def delete_report(filename: str):
    """Deletes a saved report by filename."""
    return _execute_report_deletion(filename)


@app.post("/api/reports/delete")
def delete_report_post(payload: DeleteReportPayload):
    """Deletes a saved report via POST payload."""
    return _execute_report_deletion(payload.filename)


class DiscardReportPayload(BaseModel):
    delete_file: bool = False


@app.post("/api/reports/discard")
def discard_report(payload: Optional[DiscardReportPayload] = None):
    """Unloads/discards the active report currently loaded in the Resolution Window."""
    prev_report = STATE.get("loaded_report_name")
    delete_file = payload.delete_file if payload else False

    deleted_files = []
    if delete_file and prev_report:
        cfg = load_config()
        rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
        target = (rep_dir / prev_report).resolve()
        if str(target).startswith(str(rep_dir)):
            stem = target.stem
            for ext in [".json", ".html", ".csv"]:
                sib = rep_dir / f"{stem}{ext}"
                if sib.exists() and sib.is_file():
                    try:
                        sib.unlink()
                        deleted_files.append(sib.name)
                    except Exception:
                        pass

    STATE["manga_duplicates"] = []
    STATE["doujinshi_duplicates"] = []
    STATE["video_duplicates"] = []
    STATE["manga_partials"] = []
    STATE["total_scanned"] = 0
    STATE["loaded_report_name"] = None
    STATE["status_message"] = "Report discarded. Resolution window is empty."
    add_scan_log(
        f"Active report '{prev_report or 'session'}' was discarded from the Resolution Window"
        + (f" ({len(deleted_files)} files deleted: {', '.join(deleted_files)})" if deleted_files else "") + ".",
        "WARN"
    )
    return {
        "status": "discarded",
        "previous_report": prev_report,
        "deleted_files": deleted_files
    }


# =========================================================================
# SCAN JOBS API ENDPOINTS
# =========================================================================

@app.get("/api/jobs")
def get_scan_jobs():
    """Returns all user-configured scan jobs."""
    return {"jobs": job_manager.list_jobs()}


@app.post("/api/jobs")
def create_scan_job(payload: ScanJobCreatePayload):
    """Creates a new scan job with multiple paths and custom settings."""
    try:
        new_job = job_manager.create_job(payload)
        add_scan_log(f"Created new Scan Job: '{new_job['name']}' ({new_job['target_type'].upper()}, {len(new_job['paths'])} paths)", "SUCCESS")
        return {"status": "created", "job": new_job}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/api/jobs/{job_id}")
def get_scan_job(job_id: str):
    """Retrieves a specific scan job."""
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": f"Job not found: {job_id}"})
    return {"job": job}


@app.put("/api/jobs/{job_id}")
def update_scan_job(job_id: str, payload: ScanJobUpdatePayload):
    """Updates an existing scan job."""
    try:
        updated = job_manager.update_job(job_id, payload)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    if not updated:
        return JSONResponse(status_code=404, content={"error": f"Job not found: {job_id}"})
    add_scan_log(f"Updated Scan Job: '{updated['name']}'", "INFO")
    return {"status": "updated", "job": updated}


@app.delete("/api/jobs/{job_id}")
def delete_scan_job(job_id: str):
    """Deletes a saved scan job."""
    success = job_manager.delete_job(job_id)
    if not success:
        return JSONResponse(status_code=404, content={"error": f"Job not found: {job_id}"})
    add_scan_log(f"Deleted Scan Job: {job_id}", "INFO")
    return {"status": "deleted", "job_id": job_id}


def _begin_scan(target: str, mode: str, job_id: Optional[str] = None, job_name: Optional[str] = None, queue_id: Optional[str] = None) -> None:
    """Marks a scan active before the HTTP response returns, so a second run is rejected immediately."""
    display = job_name or f"{target} ({mode}-based)"
    STATE["is_scanning"] = True
    STATE["status_message"] = f"Starting scan for {display}..."
    STATE["scan_progress"] = "Queued..."
    STATE["active_scan_info"] = {
        "target": target,
        "mode": mode,
        "job_name": job_name,
        "job_id": job_id,
        "queue_id": queue_id,
        "started_at": datetime.now().strftime("%H:%M:%S"),
        "status": "running",
        "elapsed_seconds": 0,
    }


class RunJobPayload(BaseModel):
    queue: bool = False


@app.post("/api/jobs/{job_id}/run")
def run_scan_job(job_id: str, background_tasks: BackgroundTasks, payload: Optional[RunJobPayload] = None):
    """Executes a saved scan job, or appends it when a scan is already running."""
    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": f"Job not found: {job_id}"})

    target = job.get("target_type", "manga")
    mode = job.get("mode", "name")
    paths = job.get("paths", [])
    reference_paths = job.get("reference_paths") or []
    try:
        target, mode = normalize_job_mode(target, mode)
        validate_reference_directories(target, mode, paths, reference_paths)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    entry = _new_scan_entry(
        job_name=job["name"],
        target=target,
        mode=mode,
        paths=paths,
        reference_paths=reference_paths,
        excluded_manga=job.get("excluded_manga") or [],
        job_id=job["id"],
        manga_paths=paths if target in ("manga", "all") else None,
        doujinshi_paths=paths if target in ("doujinshi", "all") else None,
    )
    result = _submit_scan(entry, background_tasks, queue=bool(payload and payload.queue))
    if result == "busy":
        return JSONResponse(status_code=409, content={"error": "A scan is already running.", "code": "busy"})
    if result == "queued":
        add_scan_log(f"Queued Scan Job '{job['name']}'.", "INFO")
        return {
            "status": "queued",
            "queue_id": entry["queue_id"],
            "job_id": job_id,
            "job_name": job["name"],
            "message": f"Scan Job '{job['name']}' added to the queue."
        }

    add_scan_log(f"Executing Scan Job '{job['name']}' across {len(paths)} locations...", "INFO")
    return {
        "status": "started",
        "queue_id": entry["queue_id"],
        "job_id": job_id,
        "job_name": job["name"],
        "message": f"Scan Job '{job['name']}' launched in background."
    }


class LoadReportPayload(BaseModel):
    filename: str


@app.post("/api/reports/load")
def load_report(payload: LoadReportPayload):
    """Loads a saved JSON report into active state for interactive review."""
    import json
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    target_file = rep_dir / payload.filename
    if not target_file.exists():
        return JSONResponse(status_code=400, content={"error": f"Report not found: {payload.filename}"})

    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Populate STATE from loaded report
    dupes_raw = data.get("duplicates", [])
    manga_dupes = []
    doujin_dupes = []
    video_dupes = []

    for d in dupes_raw:
        grp = DuplicateGroup(
            group_id=d.get("group_id", ""),
            target_type=d.get("target_type", ""),
            title=d.get("title", ""),
            sub_title=d.get("sub_title", ""),
            category=d.get("category", ""),
            items=d.get("items", []),
            recommendation=d.get("recommendation", ""),
            recommended_keep_path=d.get("recommended_keep_path", ""),
            hamming_distance=d.get("hamming_distance")
        )
        if grp.target_type == "manga":
            manga_dupes.append(grp)
        elif grp.target_type == "video":
            video_dupes.append(grp)
        else:
            doujin_dupes.append(grp)

    parts_raw = data.get("partials", [])
    partials = []
    for p in parts_raw:
        partials.append(
            PartialIssue(
                issue_id=p.get("issue_id", ""),
                series_name=p.get("series_name", ""),
                issue_type=p.get("issue_type", ""),
                description=p.get("description", ""),
                affected_items=p.get("affected_items", [])
            )
        )

    STATE["manga_duplicates"] = manga_dupes
    STATE["doujinshi_duplicates"] = doujin_dupes
    STATE["video_duplicates"] = video_dupes
    STATE["manga_partials"] = partials
    STATE["total_scanned"] = data.get("summary", {}).get("total_scanned", len(manga_dupes) + len(doujin_dupes))
    STATE["loaded_report_name"] = payload.filename
    STATE["status_message"] = f"Report '{payload.filename}' loaded into Resolution Window. Ready for review."
    add_scan_log(f"Report '{payload.filename}' loaded into Resolution Window ({len(manga_dupes) + len(doujin_dupes) + len(video_dupes)} duplicate groups).", "SUCCESS")

    return {
        "status": "loaded",
        "filename": payload.filename,
        "manga_duplicates_count": len(manga_dupes),
        "doujinshi_duplicates_count": len(doujin_dupes),
        "video_duplicates_count": len(video_dupes),
        "partials_count": len(partials)
    }


@app.get("/api/duplicates")
def get_duplicates(target: str = Query("all")):
    """Returns duplicate groups filtered by target ('manga', 'doujinshi', 'video', or 'all')."""
    res = []
    if target in ("all", "manga"):
        res.extend([d.to_dict() for d in STATE["manga_duplicates"]])
    if target in ("all", "doujinshi"):
        res.extend([d.to_dict() for d in STATE["doujinshi_duplicates"]])
    if target in ("all", "video"):
        res.extend([d.to_dict() for d in STATE.get("video_duplicates", [])])
    return res


@app.get("/api/partials")
def get_partials():
    """Returns partial chapter issues."""
    return [p.to_dict() for p in STATE["manga_partials"]]


@app.post("/api/actions/execute")
def execute_actions(payload: ExecuteActionsPayload):
    """Executes or dry-runs user-confirmed actions on duplicate files."""
    actions_dict = [a.model_dump() for a in payload.actions]
    results = action_executor.execute_plan(
        actions=actions_dict,
        dry_run=payload.dry_run,
        custom_archive_dir=payload.custom_archive_dir
    )
    return results


@app.post("/api/parse-tree")
def run_parse_tree(payload: ParseTreePayload):
    """Parses an offline tree dump text file (e.g. from sample_data/)."""
    target_path = Path(payload.file_path)
    if not target_path.exists():
        add_scan_log(f"File not found: {payload.file_path}", "ERROR")
        return JSONResponse(status_code=400, content={"error": f"File not found: {payload.file_path}"})

    add_scan_log(f"Opening offline tree dump: '{target_path.name}'...", "INFO")
    with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    add_scan_log(f"Read {len(lines):,} lines from '{target_path.name}'. Parsing directory tree...", "SCAN")
    detected_type, parsed_items = parse_tree_dump_lines(lines)
    add_scan_log(f"Detected hierarchy type: {detected_type.upper()} ({len(parsed_items):,} items parsed)", "INFO")

    if detected_type == "manga":
        add_scan_log(f"Running intra-series duplicate detection on {len(parsed_items):,} manga chapters...", "INFO")
        dupes = detect_manga_duplicates(parsed_items)
        parts = detect_manga_partials(parsed_items, check_mode="name")
        STATE["manga_duplicates"] = dupes
        STATE["manga_partials"] = parts
        STATE["total_scanned"] = len(parsed_items)
        STATE["loaded_report_name"] = f"{target_path.stem}_report.json"
        record_run_history(
            target="manga (offline)",
            mode="tree-dump",
            total_scanned=len(parsed_items),
            duplicates_count=len(dupes),
            partials_count=len(parts),
            duration_sec=0.2,
            report_file=f"{target_path.stem}_report.json",
            status="completed"
        )
        msg = f"Parsed Manga tree '{target_path.name}': {len(parsed_items):,} chapters, {len(dupes)} duplicate groups, {len(parts)} partials."
        STATE["status_message"] = msg
        add_scan_log(msg, "SUCCESS")
        return {
            "status": "success",
            "type": "manga",
            "scanned": len(parsed_items),
            "duplicates_count": len(dupes),
            "partials_count": len(parts)
        }
    else:
        add_scan_log(f"Running cross-directory duplicate detection on {len(parsed_items):,} doujinshi works...", "INFO")
        dupes = detect_doujinshi_duplicates(parsed_items)
        STATE["doujinshi_duplicates"] = dupes
        STATE["total_scanned"] = len(parsed_items)
        STATE["loaded_report_name"] = f"{target_path.stem}_report.json"
        record_run_history(
            target="doujinshi (offline)",
            mode="tree-dump",
            total_scanned=len(parsed_items),
            duplicates_count=len(dupes),
            partials_count=0,
            duration_sec=0.2,
            report_file=f"{target_path.stem}_report.json",
            status="completed"
        )
        msg = f"Parsed Doujinshi tree '{target_path.name}': {len(parsed_items):,} works, {len(dupes)} duplicate groups."
        STATE["status_message"] = msg
        add_scan_log(msg, "SUCCESS")
        return {
            "status": "success",
            "type": "doujinshi",
            "scanned": len(parsed_items),
            "duplicates_count": len(dupes),
            "partials_count": 0
        }


def _run_background_scan(target: str, mode: str, paths: Optional[List[str]], manga_paths: Optional[List[str]], doujinshi_paths: Optional[List[str]], job_id: Optional[str] = None, job_name: Optional[str] = None, excluded_manga: Optional[List[str]] = None, reference_paths: Optional[List[str]] = None, queue_id: Optional[str] = None):
    start_time = datetime.now()
    try:
        STATE["is_scanning"] = True
        display_title = job_name or f"{target} ({mode}-based)"
        STATE["status_message"] = f"Starting scan for {display_title}..."
        STATE["scan_progress"] = "Resolving target directories..."
        STATE["active_scan_info"] = {
            "target": target,
            "mode": mode,
            "job_name": job_name,
            "job_id": job_id,
            "queue_id": queue_id,
            "started_at": start_time.strftime("%H:%M:%S"),
            "status": "running",
            "elapsed_seconds": 0
        }

        add_scan_log(f"🚀 Initializing scan job: '{display_title}' (Target='{target.upper()}', Mode='{mode.upper()}')", "INFO")
        if excluded_manga:
            add_scan_log(f"Manga exclusions applied ({len(excluded_manga)} titles): {', '.join(excluded_manga[:4])}{'...' if len(excluded_manga) > 4 else ''}", "INFO")

        target, mode = normalize_job_mode(target, mode)
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["target"] = target
            STATE["active_scan_info"]["mode"] = mode

        cfg = load_config()
        if mode == "reference":
            target = "doujinshi"
            if STATE.get("active_scan_info"):
                STATE["active_scan_info"]["target"] = target
            add_scan_log("Reference job scans Doujinshi compare directories against reference directories.", "INFO")
        if target == "video":
            mode = "similar"
            if STATE.get("active_scan_info"):
                STATE["active_scan_info"]["target"] = target
                STATE["active_scan_info"]["mode"] = mode
            add_scan_log("Video job walks the whole tree and groups near-duplicate files by sampled frames.", "INFO")
        elif mode == "similar":
            raise ValueError("Similar video mode is only available for the Videos library.")

        # Parse manga paths
        m_targets: List[Path] = []
        if manga_paths:
            m_targets = [normalize_path(p) for p in manga_paths if p.strip()]
        elif target == "manga" and paths:
            m_targets = [normalize_path(p) for p in paths if p.strip()]
        else:
            # Fallback to configured or user's specific defaults
            candidate_paths = [
                "/sg2b/Share2sgb/Manga"
            ] + [str(p) for p in cfg.get("normalized_manga_paths", [])]
            for cp in candidate_paths:
                np = normalize_path(cp)
                if np.exists() and np not in m_targets:
                    m_targets.append(np)

        # Parse doujinshi paths
        d_targets: List[Path] = []
        if doujinshi_paths:
            d_targets = [normalize_path(p) for p in doujinshi_paths if p.strip()]
        elif target == "doujinshi" and paths:
            d_targets = [normalize_path(p) for p in paths if p.strip()]
        else:
            candidate_paths = [
                "/media/devmon/L500/Vere NewFolder"
            ] + [str(p) for p in cfg.get("normalized_doujinshi_paths", [])]
            for cp in candidate_paths:
                np = normalize_path(cp)
                if np.exists() and np not in d_targets:
                    d_targets.append(np)

        # If user selected 'all' and provided generic paths
        if target == "all" and paths:
            for p in paths:
                np = normalize_path(p)
                if np.exists():
                    p_lower = str(np).lower()
                    if "manga" in p_lower or "manhwa" in p_lower:
                        if np not in m_targets:
                            m_targets.append(np)
                    else:
                        if np not in d_targets:
                            d_targets.append(np)

        ref_targets: List[Path] = []
        if mode == "reference":
            m_targets = []
            d_targets = [normalize_path(p) for p in (paths or []) if p and str(p).strip()]
            ref_targets = [normalize_path(p) for p in (reference_paths or []) if p and str(p).strip()]
            if not d_targets:
                raise ValueError("At least one compare directory is required.")
            if not ref_targets:
                raise ValueError("At least one reference directory is required.")

        if target in ("manga", "all"):
            add_scan_log(f"Target Manga scan paths ({len(m_targets)}): {[str(p) for p in m_targets]}", "INFO")
        if target in ("doujinshi", "all"):
            add_scan_log(f"Target Doujinshi compare paths ({len(d_targets)}): {[str(p) for p in d_targets]}", "INFO")
        if ref_targets:
            add_scan_log(f"Reference directories ({len(ref_targets)}): {[str(p) for p in ref_targets]}", "INFO")

        v_targets: List[Path] = []
        if target == "video":
            STATE["manga_duplicates"] = []
            STATE["doujinshi_duplicates"] = []
            STATE["manga_partials"] = []
            v_targets = [normalize_path(p) for p in (paths or []) if p and str(p).strip()]
            if not v_targets:
                raise ValueError("At least one video directory is required.")
            add_scan_log(f"Target video paths ({len(v_targets)}): {[str(p) for p in v_targets]}", "INFO")
            videos = []
            for vp in v_targets:
                if vp.exists():
                    found = scan_video_tree(vp, progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl))
                    videos.extend(found)
                else:
                    add_scan_log(f"Video directory not found or unmounted: {vp}", "WARN")
            add_scan_log(f"Running near-duplicate scan on {len(videos)} videos...", "INFO")
            dupes = detect_video_duplicates(
                videos,
                progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
            )
            STATE["video_duplicates"] = dupes
            STATE["total_scanned"] = len(videos)
            add_scan_log(
                f"Detected {len(dupes)} video duplicate groups.",
                "SUCCESS" if dupes else "INFO",
            )
        else:
            STATE["video_duplicates"] = []

        # 1. Scan Manga
        if target in ("manga", "all"):
            chapters = []
            for mp in m_targets:
                if mp.exists():
                    add_scan_log(f"Walking Manga directory: '{mp.name}'...", "SCAN")
                    found = scan_manga_directory(
                        mp,
                        progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl),
                        excluded_manga=excluded_manga
                    )
                    chapters.extend(found)
                    add_scan_log(f"Accumulated {len(found)} chapters from '{mp.name}'.", "INFO")
                else:
                    add_scan_log(f"Manga directory not found or unmounted: {mp}", "WARN")

            if mode == "visual":
                add_scan_log(f"Running visual similarity scan on {len(chapters)} manga chapters (names ignored)...", "INFO")
                dupes = detect_visual_duplicates(
                    chapters,
                    target_type="manga",
                    progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                )
                parts = []
            elif mode == "exact":
                add_scan_log(f"Running exact hash check on {len(chapters)} manga chapters...", "INFO")
                dupes = detect_exact_hash_duplicates(
                    chapters,
                    target_type="manga",
                    progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                )
                parts = []
            elif mode == "missing":
                add_scan_log(f"Checking {len(chapters)} manga chapters for missing numbers...", "INFO")
                dupes = []
                parts = detect_missing_chapters(
                    chapters,
                    progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl),
                )
                STATE["doujinshi_duplicates"] = []
            else:
                add_scan_log(f"Running intra-series duplicate detector on {len(chapters)} manga chapters...", "INFO")
                dupes = detect_manga_duplicates(chapters)
                parts = detect_manga_partials(chapters, check_mode=mode)
                add_scan_log(f"Detected {len(dupes)} duplicate groups and {len(parts)} partial chapter issues.", "SUCCESS" if len(dupes) > 0 else "INFO")
                if mode == "image":
                    dupes = retain_visual_matches(
                        dupes,
                        threshold=12,
                        progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                    )

            STATE["manga_duplicates"] = dupes
            STATE["manga_partials"] = parts
            STATE["total_scanned"] = len(chapters)

        # 2. Scan Doujinshi
        if target in ("doujinshi", "all"):
            works = []
            for dp in d_targets:
                if dp.exists():
                    add_scan_log(f"Walking Doujinshi directory: '{dp.name}'...", "SCAN")
                    found = scan_doujinshi_directory(
                        dp,
                        progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl)
                    )
                    works.extend(found)
                    add_scan_log(f"Accumulated {len(found)} works from '{dp.name}'.", "INFO")
                else:
                    add_scan_log(f"Doujinshi directory not found or unmounted: {dp}", "WARN")

            if mode == "visual":
                add_scan_log(f"Running visual similarity scan on {len(works)} doujinshi works (names ignored)...", "INFO")
                dupes = detect_visual_duplicates(
                    works,
                    target_type="doujinshi",
                    progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                )
            elif mode == "exact":
                add_scan_log(f"Running exact hash check on {len(works)} doujinshi works...", "INFO")
                dupes = detect_exact_hash_duplicates(
                    works,
                    target_type="doujinshi",
                    progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                )
            elif mode == "reference":
                reference_works = []
                for rp in ref_targets:
                    if rp.exists():
                        add_scan_log(f"Walking reference directory: '{rp.name}'...", "SCAN")
                        found_ref = scan_doujinshi_directory(
                            rp,
                            progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl),
                        )
                        reference_works.extend(found_ref)
                        add_scan_log(f"Indexed {len(found_ref)} reference works from '{rp.name}'.", "INFO")
                    else:
                        add_scan_log(f"Reference directory not found or unmounted: {rp}", "WARN")
                add_scan_log(
                    f"Comparing {len(works)} compare works with {len(reference_works)} reference works by exact hash and relative path...",
                    "INFO",
                )
                dupes = detect_reference_duplicates(
                    works,
                    reference_works,
                    compare_roots=d_targets,
                    reference_roots=ref_targets,
                    progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                )
            else:
                add_scan_log(f"Running global cross-directory duplicate detector on {len(works)} doujinshi works...", "INFO")
                dupes = detect_doujinshi_duplicates(works)
                add_scan_log(f"Detected {len(dupes)} doujinshi duplicate groups across library.", "SUCCESS" if len(dupes) > 0 else "INFO")
                if mode == "image":
                    dupes = retain_visual_matches(
                        dupes,
                        threshold=12,
                        progress_callback=lambda msg, lvl="HASH": add_scan_log(msg, lvl),
                    )

            STATE["doujinshi_duplicates"] = dupes
            if target == "doujinshi":
                STATE["total_scanned"] = len(works)
            else:
                STATE["total_scanned"] += len(works)

        # Auto-export updated reports
        reports_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)
        all_dupes = STATE["manga_duplicates"] + STATE["doujinshi_duplicates"] + STATE.get("video_duplicates", [])
        all_parts = STATE["manga_partials"]

        effective_job_name = job_name or f"Manual {target.capitalize()} Scan"
        scanned_roots = v_targets if target == "video" else (m_targets + d_targets)
        report_meta = {
            "job_id": job_id or "manual",
            "job_name": effective_job_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target": target,
            "mode": mode,
            "paths": [str(p) for p in scanned_roots],
            "reference_paths": [str(p) for p in ref_targets],
        }

        slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', (job_name or "manual").lower()).strip('_') or "manual"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        primary_rep_json = f"{slug}_{ts}_report.json"
        primary_rep_html = f"{slug}_{ts}_report.html"
        primary_rep_csv = f"{slug}_{ts}_report.csv"

        add_scan_log(f"Generating reports in '{reports_dir}' ({primary_rep_json})...", "INFO")
        export_json(all_dupes, all_parts, str(reports_dir / primary_rep_json), extra_meta=report_meta)
        export_csv(all_dupes, str(reports_dir / primary_rep_csv))
        export_html(all_dupes, all_parts, STATE["total_scanned"], str(reports_dir / primary_rep_html))

        add_scan_log(f"Saved {primary_rep_json}, {primary_rep_csv}, and {primary_rep_html}", "SUCCESS")

        elapsed = round((datetime.now() - start_time).total_seconds(), 2)
        STATE["last_scan_time"] = datetime.now().isoformat()
        STATE["loaded_report_name"] = primary_rep_json

        if job_id:
            gap_count = len(all_parts) if mode == "missing" else len(all_dupes)
            job_manager.update_job_run_status(job_id, status="completed", report_file=primary_rep_json, duplicates_count=gap_count)

        record_run_history(
            target=target,
            mode=mode,
            total_scanned=STATE['total_scanned'],
            duplicates_count=len(all_dupes),
            partials_count=len(all_parts),
            duration_sec=elapsed,
            report_file=primary_rep_json,
            status="completed",
            job_name=effective_job_name,
            job_id=job_id
        )
        if mode == "missing":
            STATE["status_message"] = (
                f"Scan finished in {elapsed}s: {len(all_parts)} series with missing chapters."
            )
            add_scan_log(
                f"Scan job completed in {elapsed}s. {len(all_parts)} series have missing chapters.",
                "SUCCESS",
            )
        else:
            STATE["status_message"] = (
                f"Scan finished in {elapsed}s: {len(STATE['manga_duplicates'])} manga, "
                f"{len(STATE['doujinshi_duplicates'])} doujinshi, and "
                f"{len(STATE.get('video_duplicates', []))} video duplicate groups detected."
            )
            add_scan_log(
                f"🎉 Scan job completed in {elapsed}s! Scanned {STATE['total_scanned']} items. Found {len(all_dupes)} duplicate groups.",
                "SUCCESS"
            )
        STATE["scan_progress"] = "Scan finished successfully."
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["status"] = "completed"
            STATE["active_scan_info"]["elapsed_seconds"] = elapsed

    except ScanCancelled:
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["status"] = "cancelled"
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        if job_id:
            job_manager.update_job_run_status(job_id, status="failed")
        add_scan_log(f"❌ Scan failed with error: {e}", "ERROR")
        STATE["status_message"] = f"Scan error: {e}"
        STATE["scan_progress"] = f"Error: {e}"
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["status"] = "error"


@app.post("/api/scan")
def trigger_scan(payload: ScanPayload, background_tasks: BackgroundTasks):
    """Triggers a background scan with single or multiple custom paths."""
    try:
        target, mode = normalize_job_mode(payload.target, payload.mode)
        validate_reference_directories(target, mode, payload.paths, payload.reference_paths)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    display_name = payload.job_name or f"Quick {target} scan"
    entry = _new_scan_entry(
        job_name=display_name,
        target=target,
        mode=mode,
        paths=payload.paths,
        reference_paths=payload.reference_paths,
        excluded_manga=payload.excluded_manga,
        job_id=payload.job_id,
        manga_paths=payload.manga_paths,
        doujinshi_paths=payload.doujinshi_paths,
    )
    result = _submit_scan(entry, background_tasks, queue=bool(payload.queue))
    if result == "busy":
        return JSONResponse(status_code=409, content={"error": "A scan is already running.", "code": "busy"})
    if result == "queued":
        add_scan_log(f"Queued scan '{display_name}'.", "INFO")
        return {
            "status": "queued",
            "queue_id": entry["queue_id"],
            "message": f"Scan '{display_name}' added to the queue."
        }
    return {
        "status": "started",
        "queue_id": entry["queue_id"],
        "message": f"Scan triggered for target '{target}' using {mode}-based modality."
    }


@app.post("/api/queue/reorder")
def reorder_queue(payload: QueueReorderPayload):
    """Move a waiting scan one place up or down. The running scan stays put."""
    direction = (payload.direction or "").strip().lower()
    if direction not in ("up", "down"):
        return JSONResponse(status_code=400, content={"error": "Direction must be up or down."})
    with _SCAN_LOCK:
        queue = STATE["queue"]
        index = next((i for i, entry in enumerate(queue) if entry.get("queue_id") == payload.queue_id), None)
        if index is None:
            return JSONResponse(status_code=404, content={"error": "That job is not waiting in the queue."})
        swap = index - 1 if direction == "up" else index + 1
        if 0 <= swap < len(queue):
            queue[index], queue[swap] = queue[swap], queue[index]
        public = [_public_queue_entry(entry) for entry in queue]
    return {"status": "reordered", "queue": public}


@app.post("/api/queue/{queue_id}/cancel")
def cancel_queued_scan(queue_id: str):
    """Remove a waiting scan, or ask the running scan to stop."""
    with _SCAN_LOCK:
        running = STATE.get("running_entry")
        if STATE.get("is_scanning") and running and running.get("queue_id") == queue_id:
            _CANCEL.set()
            return {"status": "cancelling", "queue_id": queue_id}
        before = len(STATE["queue"])
        STATE["queue"] = [entry for entry in STATE["queue"] if entry.get("queue_id") != queue_id]
        if len(STATE["queue"]) == before:
            return JSONResponse(status_code=404, content={"error": "That job is not in the queue."})
    add_scan_log("Removed a job from the queue.", "INFO")
    return {"status": "removed", "queue_id": queue_id}


@app.get("/api/settings/cache")
def get_cache_settings():
    """Cache location, file count, and size. Used by the Settings page."""
    return cache_summary()


@app.post("/api/settings/cache/clear")
def clear_cache_settings():
    """Delete fingerprint cache files. Reports and scan jobs are not touched."""
    if STATE["is_scanning"]:
        return JSONResponse(status_code=400, content={"error": "A scan is running. Clear the cache after it finishes."})
    result = clear_cache()
    add_scan_log(
        f"Cleared cache at {result['path']} ({result['deleted_files']} files, {result['freed_bytes']} bytes).",
        "SUCCESS",
    )
    return {"status": "cleared", **result}


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serves the main interactive dashboard UI."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>FindDuplicates UI</h1><p>Template not found.</p>"
