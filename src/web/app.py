"""
Interactive Web Application & API Server
FastAPI backend powering the interactive dashboard inside Docker & CasaOS.
Provides endpoints to trigger scans, configure multiple scan paths, review duplicates,
and click-to-confirm file actions.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from src.config import load_config, normalize_path
from src.scanner import scan_manga_directory, scan_doujinshi_directory
from src.detector import detect_manga_duplicates, detect_manga_partials, detect_doujinshi_duplicates
from src.parser import parse_tree_dump_lines
from src.actions import ActionExecutor
from src.reporter import export_json, export_csv, export_html
from src.image_hasher import verify_chapter_similarity, compute_perceptual_hash, compute_hamming_distance
from src.models import DuplicateGroup, PartialIssue

app = FastAPI(title="FindDuplicates Dashboard", version="2.1.0")

# In-memory session state for interactive UI
STATE = {
    "is_scanning": False,
    "last_scan_time": None,
    "total_scanned": 0,
    "manga_duplicates": [],  # List[DuplicateGroup]
    "manga_partials": [],    # List[PartialIssue]
    "doujinshi_duplicates": [], # List[DuplicateGroup]
    "status_message": "Ready. No active scan running.",
    "scan_progress": "",
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
    manga_paths: Optional[List[str]] = None
    doujinshi_paths: Optional[List[str]] = None


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
    }


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
    """Returns the pre-configured docker-compose.yml content for 1-click CasaOS import."""
    compose_path = Path("docker-compose.yml")
    if compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "# docker-compose.yml not found"}


@app.get("/api/reports")
def list_reports():
    """Lists saved reports in the reports directory."""
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    reports = []
    if rep_dir.exists():
        for f in sorted(rep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            reports.append({
                "filename": f.name,
                "path": str(f),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "size_bytes": f.stat().st_size
            })
    return {"reports": reports}


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
    STATE["manga_partials"] = partials
    STATE["total_scanned"] = data.get("summary", {}).get("total_scanned", len(manga_dupes) + len(doujin_dupes))
    STATE["status_message"] = f"Report '{payload.filename}' loaded into Resolution Window. Ready for review."

    return {
        "status": "loaded",
        "filename": payload.filename,
        "manga_duplicates_count": len(manga_dupes),
        "doujinshi_duplicates_count": len(doujin_dupes),
        "partials_count": len(partials)
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


def _run_background_scan(target: str, mode: str, paths: Optional[List[str]], manga_paths: Optional[List[str]], doujinshi_paths: Optional[List[str]]):
    STATE["is_scanning"] = True
    STATE["status_message"] = f"Starting scan for {target} ({mode}-based)..."
    STATE["scan_progress"] = "Resolving directories..."

    try:
        cfg = load_config()

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
                    # Check whether path looks like manga or doujinshi
                    p_lower = str(np).lower()
                    if "manga" in p_lower or "manhwa" in p_lower:
                        if np not in m_targets:
                            m_targets.append(np)
                    else:
                        if np not in d_targets:
                            d_targets.append(np)

        # 1. Scan Manga
        if target in ("manga", "all"):
            chapters = []
            for mp in m_targets:
                if mp.exists():
                    STATE["scan_progress"] = f"Scanning Manga directory: {mp.name}..."
                    found = scan_manga_directory(mp)
                    chapters.extend(found)
                else:
                    print(f"[!] Manga directory not found: {mp}")

            STATE["scan_progress"] = f"Analyzing {len(chapters)} manga chapters for duplicates..."
            dupes = detect_manga_duplicates(chapters)
            parts = detect_manga_partials(chapters)

            if mode == "image":
                STATE["scan_progress"] = "Running visual perceptual hash verification on duplicate chapters..."
                for g in dupes:
                    if len(g.items) >= 2:
                        pa = g.items[0].get("file_path", "")
                        pb = g.items[1].get("file_path", "")
                        if pa and pb:
                            match, dist, expl = verify_chapter_similarity(pa, pb)
                            g.hamming_distance = dist
                            g.recommendation += f" [Visual Verification: {expl}]"

            STATE["manga_duplicates"] = dupes
            STATE["manga_partials"] = parts
            STATE["total_scanned"] = len(chapters)

        # 2. Scan Doujinshi
        if target in ("doujinshi", "all"):
            works = []
            for dp in d_targets:
                if dp.exists():
                    STATE["scan_progress"] = f"Scanning Doujinshi directory: {dp.name}..."
                    found = scan_doujinshi_directory(dp)
                    works.extend(found)
                else:
                    print(f"[!] Doujinshi directory not found: {dp}")

            STATE["scan_progress"] = f"Analyzing {len(works)} doujinshi works across directories..."
            dupes = detect_doujinshi_duplicates(works)

            if mode == "image":
                STATE["scan_progress"] = "Extracting cover perceptual hashes..."
                hashes = {}
                for w in works:
                    if w.file_path:
                        h = compute_perceptual_hash(w.file_path, 0)
                        if h:
                            hashes[w.file_path] = h
                for g in dupes:
                    if len(g.items) >= 2:
                        pa = g.items[0].get("file_path", "")
                        pb = g.items[1].get("file_path", "")
                        if pa in hashes and pb in hashes:
                            dist = compute_hamming_distance(hashes[pa], hashes[pb])
                            g.hamming_distance = dist
                            if dist is not None:
                                g.recommendation += f" [Cover Distance: {dist}]"

            STATE["doujinshi_duplicates"] = dupes
            if target == "doujinshi":
                STATE["total_scanned"] = len(works)
            else:
                STATE["total_scanned"] += len(works)

        # Auto-export updated reports
        reports_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)
        all_dupes = STATE["manga_duplicates"] + STATE["doujinshi_duplicates"]
        all_parts = STATE["manga_partials"]
        export_json(all_dupes, all_parts, str(reports_dir / "latest_report.json"))
        export_csv(all_dupes, str(reports_dir / "latest_report.csv"))
        export_html(all_dupes, all_parts, STATE["total_scanned"], str(reports_dir / "latest_report.html"))

        STATE["last_scan_time"] = datetime.now().isoformat()
        STATE["status_message"] = (
            f"Scan finished: {len(STATE['manga_duplicates'])} manga and "
            f"{len(STATE['doujinshi_duplicates'])} doujinshi duplicate groups detected."
        )
        STATE["scan_progress"] = "Scan finished successfully."

    except Exception as e:
        STATE["status_message"] = f"Scan error: {e}"
        STATE["scan_progress"] = f"Error: {e}"
    finally:
        STATE["is_scanning"] = False


@app.post("/api/scan")
def trigger_scan(payload: ScanPayload, background_tasks: BackgroundTasks):
    """Triggers a background scan with single or multiple custom paths."""
    if STATE["is_scanning"]:
        return JSONResponse(status_code=400, content={"error": "A scan is already in progress. Please wait."})

    background_tasks.add_task(
        _run_background_scan,
        target=payload.target,
        mode=payload.mode,
        paths=payload.paths,
        manga_paths=payload.manga_paths,
        doujinshi_paths=payload.doujinshi_paths
    )
    return {
        "status": "started",
        "message": f"Scan triggered for target '{payload.target}' using {payload.mode}-based modality."
    }


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serves the main interactive dashboard UI."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>FindDuplicates UI</h1><p>Template not found.</p>"
