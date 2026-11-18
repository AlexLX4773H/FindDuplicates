"""
Main Application Entrypoint
Unified CLI and Interactive Web Server runner for FindDuplicates.
Supports specialized jobs:
- manga: Intra-series duplicate & partial chapter detector (name or image based).
- doujinshi: Global cross-directory doujinshi duplicate detector (name or image based).
- parse-tree: Offline analyzer for Windows tree /a and tree /f dump files.
- server: Interactive web dashboard with click-and-confirm duplicate resolution.
"""

import argparse
import sys
import os
from pathlib import Path

from src.config import load_config, normalize_path
from src.scanner import scan_manga_directory, scan_doujinshi_directory
from src.detector import detect_manga_duplicates, detect_manga_partials, detect_doujinshi_duplicates
from src.parser import parse_tree_dump_lines
from src.reporter import export_terminal, export_json, export_csv, export_html
from src.image_hasher import verify_chapter_similarity, compute_perceptual_hash, compute_hamming_distance


def run_manga_job(args, cfg):
    output_dir = Path(args.output or cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    scan_paths = [normalize_path(p) for p in args.scan_paths] if args.scan_paths else cfg.get("normalized_scan_paths", [])
    if not scan_paths:
        print("[!] No scan paths specified. Use --scan <path> or configure config.yaml.")
        sys.exit(1)

    print(f"[*] Starting Manga scan ({args.by}-based) across {len(scan_paths)} root path(s)...")
    chapters = []
    for p in scan_paths:
        if p.exists():
            chapters.extend(scan_manga_directory(p, progress_callback=lambda msg, lvl="INFO": print(f"[{lvl}] {msg}")))
        else:
            print(f"[!] Path not found: {p}")

    print(f"[*] Discovered {len(chapters)} chapter items.")
    print("[*] Running intra-series detection...")

    duplicates = detect_manga_duplicates(chapters)
    partials = detect_manga_partials(chapters, min_page_ratio=cfg.get("detection", {}).get("min_page_ratio", 0.60))

    if args.by == "image":
        print("[*] Running image perceptual hash verification on duplicate chapter candidates...")
        for g in duplicates:
            if len(g.items) >= 2:
                p_a = g.items[0].get("file_path", "")
                p_b = g.items[1].get("file_path", "")
                if p_a and p_b:
                    match, dist, expl = verify_chapter_similarity(p_a, p_b)
                    g.hamming_distance = dist
                    g.recommendation += f" [Visual Verification: {expl}]"

    # Export reports
    export_terminal(duplicates, partials, len(chapters))
    export_json(duplicates, partials, str(output_dir / "manga_duplicates.json"))
    export_csv(duplicates, str(output_dir / "manga_duplicates.csv"))
    export_html(duplicates, partials, len(chapters), str(output_dir / "manga_duplicates.html"))
    print(f"[+] Reports saved to: {output_dir}")
    print("[INFO] Safety Guarantee: Scans run in strictly READ-ONLY mode. No files were modified, moved, or deleted.")
    print("[INFO] To review duplicates and resolve them, open the Web Dashboard at http://localhost:8765")


def run_doujinshi_job(args, cfg):
    output_dir = Path(args.output or cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    scan_paths = [normalize_path(p) for p in args.scan_paths] if args.scan_paths else cfg.get("normalized_scan_paths", [])
    if not scan_paths:
        print("[!] No scan paths specified. Use --scan <path> or configure config.yaml.")
        sys.exit(1)

    print(f"[*] Starting Doujinshi global cross-directory scan ({args.by}-based)...")
    works = []
    for p in scan_paths:
        if p.exists():
            works.extend(scan_doujinshi_directory(p, progress_callback=lambda msg, lvl="INFO": print(f"[{lvl}] {msg}")))
        else:
            print(f"[!] Path not found: {p}")

    print(f"[*] Discovered {len(works)} doujinshi works across library.")
    print("[*] Running cross-directory duplicate detection...")

    duplicates = detect_doujinshi_duplicates(works)

    if args.by == "image":
        print("[*] Indexing cover perceptual hashes for visual clustering...")
        # Optional image perceptual hash matching for doujinshi
        hashes = {}
        for w in works:
            if w.file_path:
                h = compute_perceptual_hash(w.file_path, 0)
                if h:
                    hashes[w.file_path] = (h, w)
        # Verify flagged duplicates
        for g in duplicates:
            if len(g.items) >= 2:
                pa = g.items[0].get("file_path", "")
                pb = g.items[1].get("file_path", "")
                if pa in hashes and pb in hashes:
                    dist = compute_hamming_distance(hashes[pa][0], hashes[pb][0])
                    g.hamming_distance = dist
                    if dist is not None:
                        g.recommendation += f" [Cover Hamming Distance: {dist}]"

    export_terminal(duplicates, [], len(works))
    export_json(duplicates, [], str(output_dir / "doujinshi_duplicates.json"))
    export_csv(duplicates, str(output_dir / "doujinshi_duplicates.csv"))
    export_html(duplicates, [], len(works), str(output_dir / "doujinshi_duplicates.html"))
    print(f"[+] Reports saved to: {output_dir}")
    print("[INFO] Safety Guarantee: Scans run in strictly READ-ONLY mode. No files were modified, moved, or deleted.")
    print("[INFO] To review duplicates and resolve them, open the Web Dashboard at http://localhost:8765")


def run_parse_tree_job(args, cfg):
    target_file = Path(args.file).resolve()
    if not target_file.exists():
        print(f"[!] Dump file not found: {target_file}")
        sys.exit(1)

    output_dir = Path(args.output or cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Parsing offline tree dump: {target_file.name}...")
    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    detected_type, items = parse_tree_dump_lines(lines)
    tree_type = args.type if args.type != "auto" else detected_type

    print(f"[*] Detected tree type: {tree_type.upper()} ({len(items)} items parsed)")

    if tree_type == "manga":
        duplicates = detect_manga_duplicates(items)
        partials = detect_manga_partials(items)
        export_terminal(duplicates, partials, len(items))
        export_json(duplicates, partials, str(output_dir / f"{target_file.stem}_report.json"))
        export_csv(duplicates, str(output_dir / f"{target_file.stem}_report.csv"))
        export_html(duplicates, partials, len(items), str(output_dir / f"{target_file.stem}_report.html"))
    else:
        duplicates = detect_doujinshi_duplicates(items)
        export_terminal(duplicates, [], len(items))
        export_json(duplicates, [], str(output_dir / f"{target_file.stem}_report.json"))
        export_csv(duplicates, str(output_dir / f"{target_file.stem}_report.csv"))
        export_html(duplicates, [], len(items), str(output_dir / f"{target_file.stem}_report.html"))

    print(f"[+] Offline report saved to: {output_dir}")
    print("[INFO] Safety Guarantee: Scans run in strictly READ-ONLY mode. No files were modified, moved, or deleted.")
    print("[INFO] To review duplicates and resolve them, open the Web Dashboard at http://localhost:8765")


def run_server_job(args, cfg):
    host = args.host or os.getenv("HOST", "0.0.0.0")
    port = int(args.port or os.getenv("PORT", 8765))
    print(f"[*] Starting FindDuplicates Interactive Web Server on http://{host}:{port} ...")
    try:
        import uvicorn
        from src.web.app import app
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError:
        print("[!] uvicorn is required for the web server. Install with 'pip install uvicorn'.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="FindDuplicates: Manga & Doujinshi Duplicate Finder"
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. Manga subcommand
    p_manga = subparsers.add_parser("manga", help="Intra-series manga duplicate & partial scanner")
    p_manga.add_argument("--by", choices=["name", "image"], default="name", help="Detection modality (name or image)")
    p_manga.add_argument("--scan", action="append", dest="scan_paths", help="Scan path (can be repeated)")
    p_manga.add_argument("--output", help="Output directory for reports")

    # 2. Doujinshi subcommand
    p_doujin = subparsers.add_parser("doujinshi", help="Global cross-directory doujinshi duplicate scanner")
    p_doujin.add_argument("--by", choices=["name", "image"], default="name", help="Detection modality (name or image)")
    p_doujin.add_argument("--scan", action="append", dest="scan_paths", help="Scan path (can be repeated)")
    p_doujin.add_argument("--output", help="Output directory for reports")

    # 3. Parse Tree subcommand
    p_tree = subparsers.add_parser("parse-tree", help="Offline analyzer for tree dump text files")
    p_tree.add_argument("--file", required=True, help="Path to tree dump text file")
    p_tree.add_argument("--type", choices=["auto", "manga", "doujinshi"], default="auto", help="Structure type")
    p_tree.add_argument("--output", help="Output directory for reports")

    # 4. Server subcommand
    p_server = subparsers.add_parser("server", help="Launch interactive web UI dashboard")
    p_server.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_server.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")

    args = parser.parse_args()
    cfg = load_config(args.config)

    if args.command == "manga":
        run_manga_job(args, cfg)
    elif args.command == "doujinshi":
        run_doujinshi_job(args, cfg)
    elif args.command == "parse-tree":
        run_parse_tree_job(args, cfg)
    elif args.command == "server":
        run_server_job(args, cfg)
    else:
        # If run without subcommand: check if UI is requested or launch server
        print("[*] No subcommand specified. Defaulting to interactive server mode...")
        print("    (Use --help to see all available CLI subcommands)")
        class ServerArgs:
            host = "0.0.0.0"
            port = 8765
        run_server_job(ServerArgs(), cfg)


if __name__ == "__main__":
    main()
