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
    "logs": [],              # List[Dict[str, Any]]
    "active_scan_info": None, # Optional[Dict[str, Any]]
    "loaded_report_name": "latest_report.json",
    "run_history": [],       # List[Dict[str, Any]]
}

_LOG_ID_COUNTER = 0

def add_scan_log(message: str, level: str = "INFO"):
    """Appends a timestamped log entry to STATE with level tags."""
    global _LOG_ID_COUNTER
    _LOG_ID_COUNTER += 1
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "id": _LOG_ID_COUNTER,
        "time": timestamp,
        "level": level.upper(),  # INFO, SCAN, HASH, WARN, ERROR, SUCCESS
        "message": message
    }
    STATE["logs"].append(entry)
    if len(STATE["logs"]) > 1000:
        STATE["logs"] = STATE["logs"][-1000:]
    STATE["scan_progress"] = message
    print(f"[{timestamp}] [{level.upper()}] {message}")


def record_run_history(target: str, mode: str, total_scanned: int, duplicates_count: int, partials_count: int, duration_sec: float, report_file: str, status: str = "completed"):
    """Records completed scan runs in persistent history."""
    entry = {
        "id": f"run_{len(STATE['run_history']) + 1}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": target,
        "mode": mode,
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
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    jdata = json.load(jf)
                    dupes = len(jdata.get("duplicates", []))
                    parts = len(jdata.get("partials", []))
                    scanned = jdata.get("summary", {}).get("total_scanned", dupes)
                    target = "manga" if "manga" in f.name.lower() else "doujinshi"
                    STATE["run_history"].append({
                        "id": f"run_hist_{idx}",
                        "timestamp": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "target": target,
                        "mode": "name",
                        "total_scanned": scanned,
                        "duplicates_count": dupes,
                        "partials_count": parts,
                        "duration_seconds": 1.5,
                        "report_file": f.name,
                        "status": "completed"
                    })
            except Exception:
                pass
    except Exception:
        pass

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
        "active_scan_info": STATE.get("active_scan_info"),
        "loaded_report_name": STATE.get("loaded_report_name", "latest_report.json"),
        "run_history_count": len(STATE.get("run_history", [])),
        "logs": STATE["logs"][-150:],
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
    """Lists saved reports with metadata, duplicate counts, and available export formats."""
    import json
    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    reports = []
    if rep_dir.exists():
        for f in sorted(rep_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            dupes_count = 0
            partials_count = 0
            scanned_count = 0
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    jdata = json.load(jf)
                    dupes_count = len(jdata.get("duplicates", []))
                    partials_count = len(jdata.get("partials", []))
                    scanned_count = jdata.get("summary", {}).get("total_scanned", dupes_count)
            except Exception:
                pass

            stem = f.stem
            html_file = rep_dir / f"{stem}.html"
            csv_file = rep_dir / f"{stem}.csv"

            reports.append({
                "filename": f.name,
                "stem": stem,
                "path": str(f),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
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
        "loaded_report_name": STATE.get("loaded_report_name", "latest_report.json"),
        "run_history": STATE.get("run_history", [])
    }


@app.get("/api/run-history")
def get_run_history():
    """Returns past scan execution runs and active report info."""
    return {
        "run_history": STATE.get("run_history", []),
        "loaded_report_name": STATE.get("loaded_report_name", "latest_report.json")
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
    STATE["loaded_report_name"] = payload.filename
    STATE["status_message"] = f"Report '{payload.filename}' loaded into Resolution Window. Ready for review."
    add_scan_log(f"Report '{payload.filename}' loaded into Resolution Window ({len(manga_dupes) + len(doujin_dupes)} duplicate groups).", "SUCCESS")

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
        parts = detect_manga_partials(parsed_items)
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


def _run_background_scan(target: str, mode: str, paths: Optional[List[str]], manga_paths: Optional[List[str]], doujinshi_paths: Optional[List[str]]):
    start_time = datetime.now()
    STATE["is_scanning"] = True
    STATE["status_message"] = f"Starting scan for {target} ({mode}-based)..."
    STATE["scan_progress"] = "Resolving target directories..."
    STATE["active_scan_info"] = {
        "target": target,
        "mode": mode,
        "started_at": start_time.strftime("%H:%M:%S"),
        "status": "running",
        "elapsed_seconds": 0
    }

    add_scan_log(f"🚀 Initializing scan job: Target='{target.upper()}', Mode='{mode.upper()}'", "INFO")

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
                    p_lower = str(np).lower()
                    if "manga" in p_lower or "manhwa" in p_lower:
                        if np not in m_targets:
                            m_targets.append(np)
                    else:
                        if np not in d_targets:
                            d_targets.append(np)

        if target in ("manga", "all"):
            add_scan_log(f"Target Manga scan paths ({len(m_targets)}): {[str(p) for p in m_targets]}", "INFO")
        if target in ("doujinshi", "all"):
            add_scan_log(f"Target Doujinshi scan paths ({len(d_targets)}): {[str(p) for p in d_targets]}", "INFO")

        # 1. Scan Manga
        if target in ("manga", "all"):
            chapters = []
            for mp in m_targets:
                if mp.exists():
                    add_scan_log(f"Walking Manga directory: '{mp.name}'...", "SCAN")
                    found = scan_manga_directory(
                        mp,
                        progress_callback=lambda msg, lvl="SCAN": add_scan_log(msg, lvl)
                    )
                    chapters.extend(found)
                    add_scan_log(f"Accumulated {len(found)} chapters from '{mp.name}'.", "INFO")
                else:
                    add_scan_log(f"Manga directory not found or unmounted: {mp}", "WARN")

            add_scan_log(f"Running intra-series duplicate detector on {len(chapters)} manga chapters...", "INFO")
            dupes = detect_manga_duplicates(chapters)
            parts = detect_manga_partials(chapters)
            add_scan_log(f"Detected {len(dupes)} duplicate groups and {len(parts)} partial chapter issues.", "SUCCESS" if len(dupes) > 0 else "INFO")

            if mode == "image":
                add_scan_log(f"Starting visual perceptual hash (dHash/pHash) verification on {len(dupes)} candidate groups...", "HASH")
                for idx, g in enumerate(dupes, 1):
                    if len(g.items) >= 2:
                        pa = g.items[0].get("file_path", "")
                        pb = g.items[1].get("file_path", "")
                        if pa and pb:
                            add_scan_log(f"Comparing artwork for '{g.title}' {g.sub_title}...", "HASH")
                            match, dist, expl = verify_chapter_similarity(pa, pb)
                            g.hamming_distance = dist
                            g.recommendation += f" [Visual Verification: {expl}]"
                            add_scan_log(f"Result: Hamming distance {dist} ({expl})", "SUCCESS" if match else "WARN")

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

            add_scan_log(f"Running global cross-directory duplicate detector on {len(works)} doujinshi works...", "INFO")
            dupes = detect_doujinshi_duplicates(works)
            add_scan_log(f"Detected {len(dupes)} doujinshi duplicate groups across library.", "SUCCESS" if len(dupes) > 0 else "INFO")

            if mode == "image":
                add_scan_log(f"Extracting cover perceptual hashes across {len(works)} doujinshi works...", "HASH")
                hashes = {}
                for idx, w in enumerate(works, 1):
                    if w.file_path:
                        h = compute_perceptual_hash(w.file_path, 0)
                        if h:
                            hashes[w.file_path] = h
                        if idx % 50 == 0 or idx == len(works):
                            add_scan_log(f"Cover hash progress: {idx}/{len(works)} processed...", "HASH")

                for g in dupes:
                    if len(g.items) >= 2:
                        pa = g.items[0].get("file_path", "")
                        pb = g.items[1].get("file_path", "")
                        if pa in hashes and pb in hashes:
                            dist = compute_hamming_distance(hashes[pa], hashes[pb])
                            g.hamming_distance = dist
                            if dist is not None:
                                g.recommendation += f" [Cover Distance: {dist}]"
                                add_scan_log(f"Cover Hamming distance for '{g.title}': {dist}", "HASH")

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

        add_scan_log(f"Generating reports in '{reports_dir}'...", "INFO")
        export_json(all_dupes, all_parts, str(reports_dir / "latest_report.json"))
        export_csv(all_dupes, str(reports_dir / "latest_report.csv"))
        export_html(all_dupes, all_parts, STATE["total_scanned"], str(reports_dir / "latest_report.html"))
        add_scan_log("Saved latest_report.json, latest_report.csv, and latest_report.html", "SUCCESS")

        elapsed = round((datetime.now() - start_time).total_seconds(), 2)
        STATE["last_scan_time"] = datetime.now().isoformat()
        STATE["loaded_report_name"] = "latest_report.json"
        record_run_history(
            target=target,
            mode=mode,
            total_scanned=STATE['total_scanned'],
            duplicates_count=len(all_dupes),
            partials_count=len(all_parts),
            duration_sec=elapsed,
            report_file="latest_report.json",
            status="completed"
        )
        STATE["status_message"] = (
            f"Scan finished in {elapsed}s: {len(STATE['manga_duplicates'])} manga and "
            f"{len(STATE['doujinshi_duplicates'])} doujinshi duplicate groups detected."
        )
        STATE["scan_progress"] = "Scan finished successfully."
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["status"] = "completed"
            STATE["active_scan_info"]["elapsed_seconds"] = elapsed

        add_scan_log(
            f"🎉 Scan job completed in {elapsed}s! Scanned {STATE['total_scanned']} items. Found {len(all_dupes)} duplicate groups.",
            "SUCCESS"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        add_scan_log(f"❌ Scan failed with error: {e}", "ERROR")
        STATE["status_message"] = f"Scan error: {e}"
        STATE["scan_progress"] = f"Error: {e}"
        if STATE.get("active_scan_info"):
            STATE["active_scan_info"]["status"] = "error"
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
