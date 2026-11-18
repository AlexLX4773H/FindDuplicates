"""
Report Generator Module
Exports detection results into Terminal tables, JSON, CSV, and interactive HTML.
"""

import json
import csv
import os
from pathlib import Path
from typing import List
from src.detector import DuplicateGroup, PartialIssue

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manga Duplicate & Partial Chapter Report</title>
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #f43f5e;
            --accent-cyan: #38bdf8;
            --border: #334155;
            --badge-dup: #e11d48;
            --badge-partial: #f59e0b;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header { border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; margin-bottom: 2rem; }
        h1 { margin: 0 0 0.5rem 0; font-size: 2rem; color: #ffffff; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
        }
        .stat-val { font-size: 2rem; font-weight: bold; color: var(--accent-cyan); }
        .stat-label { font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; }
        .section-title { font-size: 1.4rem; margin: 2rem 0 1rem 0; color: #e2e8f0; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 2rem;
            border: 1px solid var(--border);
        }
        th, td { padding: 12px 16px; text-align: left; }
        th { background: #162032; color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; }
        tr:not(:last-child) { border-bottom: 1px solid var(--border); }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-dup { background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid #f43f5e; }
        .badge-partial { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
        .path { font-family: monospace; font-size: 0.82rem; color: var(--text-muted); word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Manga &amp; Doujinshi Duplicate Finder</h1>
            <p style="color: var(--text-muted); margin: 0;">Scan Results &amp; Chapter Health Audit</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-val">__DUP_COUNT__</div>
                <div class="stat-label">Duplicate Chapter Groups</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #fbbf24;">__PARTIAL_COUNT__</div>
                <div class="stat-label">Partial / Fractional Issues</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #10b981;">__TOTAL_SCANNED__</div>
                <div class="stat-label">Total Chapters Scanned</div>
            </div>
        </div>

        <h2 class="section-title">Duplicate Chapters</h2>
        <table>
            <thead>
                <tr>
                    <th>Series</th>
                    <th>Chapter</th>
                    <th>Category</th>
                    <th>Count</th>
                    <th>Instances &amp; File Paths</th>
                </tr>
            </thead>
            <tbody>
                __DUP_ROWS__
            </tbody>
        </table>

        <h2 class="section-title">Partial &amp; Incomplete Releases</h2>
        <table>
            <thead>
                <tr>
                    <th>Series</th>
                    <th>Issue Type</th>
                    <th>Details</th>
                    <th>Affected Paths</th>
                </tr>
            </thead>
            <tbody>
                __PARTIAL_ROWS__
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def export_terminal(duplicates: List[DuplicateGroup], partials: List[PartialIssue], total_scanned: int):
    """Outputs summary cleanly to stdout."""
    print("=" * 80)
    print(" MANGA & DOUJINSHI DUPLICATE & PARTIAL CHAPTER FINDER ")
    print("=" * 80)
    print(f"Total Chapters Analyzed: {total_scanned}")
    print(f"Duplicate Groups Found : {len(duplicates)}")
    print(f"Partial Issues Found   : {len(partials)}")
    print("-" * 80)

    if duplicates:
        print("\n[DUPLICATES DETECTED]")
        for dg in duplicates:
            print(f"  * Series: {dg.series_name} | Chapter: {dg.chapter_num} [{dg.category}]")
            for c in dg.chapters:
                grp = f"[{c.scanlator_group}] " if c.scanlator_group else ""
                print(f"      - {grp}{c.raw_name} ({c.page_count} pages) -> {c.file_path}")

    if partials:
        print("\n[PARTIAL / INCOMPLETE CHAPTERS DETECTED]")
        for p in partials:
            print(f"  * Series: {p.series_name} | Type: {p.issue_type}")
            print(f"      Description: {p.description}")
            for c in p.affected_chapters:
                print(f"      - {c.raw_name} -> {c.file_path}")
    print("=" * 80)

def export_json(duplicates: List[DuplicateGroup], partials: List[PartialIssue], output_path: str):
    """Exports structured JSON data."""
    data = {
        "duplicates": [
            {
                "series": dg.series_name,
                "chapter_num": dg.chapter_num,
                "category": dg.category,
                "recommendation": dg.recommendation,
                "copies": [
                    {
                        "raw_name": c.raw_name,
                        "scanlator": c.scanlator_group,
                        "pages": c.page_count,
                        "path": c.file_path,
                    }
                    for c in dg.chapters
                ]
            }
            for dg in duplicates
        ],
        "partials": [
            {
                "series": p.series_name,
                "issue_type": p.issue_type,
                "description": p.description,
                "affected_files": [c.file_path for c in p.affected_chapters]
            }
            for p in partials
        ]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def export_html(duplicates: List[DuplicateGroup], partials: List[PartialIssue], total_scanned: int, output_path: str):
    """Exports an interactive HTML dashboard report."""
    dup_rows = []
    for dg in duplicates:
        paths_html = "<br>".join([f"<span class='path'>{c.raw_name} ({c.page_count} pgs): {c.file_path}</span>" for c in dg.chapters])
        dup_rows.append(
            f"<tr>"
            f"<td><strong>{dg.series_name}</strong></td>"
            f"<td>Ch. {dg.chapter_num}</td>"
            f"<td><span class='badge badge-dup'>{dg.category}</span></td>"
            f"<td>{len(dg.chapters)}</td>"
            f"<td>{paths_html}</td>"
            f"</tr>"
        )

    partial_rows = []
    for p in partials:
        paths_html = "<br>".join([f"<span class='path'>{c.raw_name}: {c.file_path}</span>" for c in p.affected_chapters])
        partial_rows.append(
            f"<tr>"
            f"<td><strong>{p.series_name}</strong></td>"
            f"<td><span class='badge badge-partial'>{p.issue_type}</span></td>"
            f"<td>{p.description}</td>"
            f"<td>{paths_html}</td>"
            f"</tr>"
        )

    html = HTML_TEMPLATE.replace("__DUP_COUNT__", str(len(duplicates)))
    html = html.replace("__PARTIAL_COUNT__", str(len(partials)))
    html = html.replace("__TOTAL_SCANNED__", str(total_scanned))
    html = html.replace("__DUP_ROWS__", "\n".join(dup_rows) if dup_rows else "<tr><td colspan='5'>No duplicates found!</td></tr>")
    html = html.replace("__PARTIAL_ROWS__", "\n".join(partial_rows) if partial_rows else "<tr><td colspan='4'>No partial issues found!</td></tr>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
