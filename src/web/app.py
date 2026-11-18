"""
Interactive Web Application & API Server
FastAPI backend powering the interactive dashboard inside Docker & CasaOS.
Provides endpoints to trigger scans, review duplicates, and click-to-confirm file actions.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import load_config, normalize_path
from src.scanner import scan_manga_directory, scan_doujinshi_directory
from src.detector import detect_manga_duplicates, detect_manga_partials, detect_doujinshi_duplicates
from src.parser import parse_tree_dump_lines
from src.actions import ActionExecutor
from src.models import DuplicateGroup, PartialIssue

app = FastAPI(title="FindDuplicates Dashboard", version="2.0.0")

# In-memory session state for interactive UI
STATE = {
    "is_scanning": False,
    "last_scan_time": None,
    "total_scanned": 0,
    "manga_duplicates": [],  # List[DuplicateGroup]
    "manga_partials": [],    # List[PartialIssue]
    "doujinshi_duplicates": [], # List[DuplicateGroup]
    "status_message": "Ready. No active scan running.",
    "active_reports": [],
}

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
    target: str = "manga"  # 'manga', 'doujinshi', 'all'
    mode: str = "name"     # 'name', 'image'
    paths: Optional[List[str]] = None


@app.get("/api/state")
def get_state():
    """Returns the current state and duplicate statistics."""
    return {
        "is_scanning": STATE["is_scanning"],
        "last_scan_time": STATE["last_scan_time"],
        "total_scanned": STATE["total_scanned"],
        "status_message": STATE["status_message"],
        "manga_duplicates_count": len(STATE["manga_duplicates"]),
        "manga_partials_count": len(STATE["manga_partials"]),
        "doujinshi_duplicates_count": len(STATE["doujinshi_duplicates"]),
    }


@app.get("/api/duplicates")
def get_duplicates(target: str = Query("all")):
    """Returns duplicate groups filtered by target ('manga', 'doujinshi', or 'all')."""
    res = []
    if target in ("all", "manga"):
        res.extend([d.to_dict() for d in STATE["manga_duplicates"]])
    if target in ("all", "doujinshi"):
        res.extend([d.to_dict() for d in STATE["doujinshi_duplicates"]])
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
        return JSONResponse(status_code=400, content={"error": f"File not found: {payload.file_path}"})

    with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    detected_type, parsed_items = parse_tree_dump_lines(lines)

    if detected_type == "manga":
        dupes = detect_manga_duplicates(parsed_items)
        parts = detect_manga_partials(parsed_items)
        STATE["manga_duplicates"] = dupes
        STATE["manga_partials"] = parts
        STATE["total_scanned"] = len(parsed_items)
        STATE["status_message"] = f"Parsed Manga tree '{target_path.name}': {len(parsed_items)} chapters, {len(dupes)} duplicate groups."
        return {
            "status": "success",
            "type": "manga",
            "scanned": len(parsed_items),
            "duplicates_count": len(dupes),
            "partials_count": len(parts)
        }
    else:
        dupes = detect_doujinshi_duplicates(parsed_items)
        STATE["doujinshi_duplicates"] = dupes
        STATE["total_scanned"] = len(parsed_items)
        STATE["status_message"] = f"Parsed Doujinshi tree '{target_path.name}': {len(parsed_items)} works, {len(dupes)} duplicate groups."
        return {
            "status": "success",
            "type": "doujinshi",
            "scanned": len(parsed_items),
            "duplicates_count": len(dupes),
            "partials_count": 0
        }


def _run_background_scan(target: str, mode: str, paths: Optional[List[str]]):
    STATE["is_scanning"] = True
    STATE["status_message"] = f"Scanning {target} ({mode}-based)..."
    try:
        cfg = load_config()
        if not paths:
            paths = cfg.get("normalized_scan_paths", [])
        else:
            paths = [normalize_path(p) for p in paths]

        if target in ("manga", "all"):
            chapters = []
            for p in paths:
                if p.exists():
                    chapters.extend(scan_manga_directory(p))
            STATE["manga_duplicates"] = detect_manga_duplicates(chapters)
            STATE["manga_partials"] = detect_manga_partials(chapters)
            STATE["total_scanned"] += len(chapters)

        if target in ("doujinshi", "all"):
            works = []
            for p in paths:
                if p.exists():
                    works.extend(scan_doujinshi_directory(p))
            STATE["doujinshi_duplicates"] = detect_doujinshi_duplicates(works)
            STATE["total_scanned"] += len(works)

        STATE["status_message"] = f"Scan complete. Found {len(STATE['manga_duplicates'])} manga and {len(STATE['doujinshi_duplicates'])} doujinshi duplicate groups."
    except Exception as e:
        STATE["status_message"] = f"Scan error: {e}"
    finally:
        STATE["is_scanning"] = False


@app.post("/api/scan")
def trigger_scan(payload: ScanPayload, background_tasks: BackgroundTasks):
    """Triggers a background scan."""
    if STATE["is_scanning"]:
        return JSONResponse(status_code=400, content={"error": "A scan is already in progress."})

    background_tasks.add_task(_run_background_scan, payload.target, payload.mode, payload.paths)
    return {"status": "started", "message": f"Scan triggered for {payload.target}"}


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serves the main interactive dashboard UI."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>FindDuplicates UI</h1><p>Template not found.</p>"
