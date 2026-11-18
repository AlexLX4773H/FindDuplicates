"""
Main Application Entrypoint
CLI and automated runner for Manga & Doujinshi duplicate and partial chapter finder.
"""

import argparse
import os
import sys
from pathlib import Path
from src.config import load_config, normalize_path
from src.scanner import scan_manga_directory
from src.detector import detect_duplicates, detect_partials
from src.reporter import export_terminal, export_json, export_html

def main():
    parser = argparse.ArgumentParser(
        description="Manga & Doujinshi Duplicate and Partial Chapter Finder"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--scan",
        action="append",
        dest="cli_scan_paths",
        help="Specify directories to scan (can be repeated for multiple paths)"
    )
    parser.add_argument(
        "--output",
        help="Output directory for reports (overrides config)"
    )

    args = parser.parse_args()

    # Load base configuration
    cfg = load_config(args.config)

    # CLI scan path overrides
    if args.cli_scan_paths:
        scan_paths = [normalize_path(p) for p in args.cli_scan_paths]
    else:
        scan_paths = cfg.get("normalized_scan_paths", [])

    output_dir = Path(args.output or cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not scan_paths:
        print("[!] No scan paths specified.")
        print("    Provide paths via '--scan <path>', config.yaml, or SCAN_PATHS environment variable.")
        sys.exit(1)

    print(f"[*] Starting scan across {len(scan_paths)} root location(s):")
    for p in scan_paths:
        print(f"    - {p} ({'FOUND' if p.exists() else 'NOT FOUND'})")

    all_chapters = []
    for p in scan_paths:
        if p.exists():
            chapters = scan_manga_directory(p)
            all_chapters.extend(chapters)

    print(f"\n[*] Discovered {len(all_chapters)} chapter items.")
    print("[*] Running duplicate & partial chapter detection engine...")

    duplicates = detect_duplicates(all_chapters)
    partials = detect_partials(all_chapters, min_page_ratio=cfg.get("detection", {}).get("min_page_ratio", 0.60))

    formats = cfg.get("output", {}).get("formats", ["terminal", "html", "json"])

    if "terminal" in formats:
        export_terminal(duplicates, partials, len(all_chapters))

    if "json" in formats:
        json_file = output_dir / "manga_duplicates_report.json"
        export_json(duplicates, partials, str(json_file))
        print(f"[+] JSON report saved to: {json_file}")

    if "html" in formats:
        html_file = output_dir / "manga_duplicates_report.html"
        export_html(duplicates, partials, len(all_chapters), str(html_file))
        print(f"[+] HTML report saved to: {html_file}")

if __name__ == "__main__":
    main()
