"""
Report Generation & Export Module
Exports duplicate and partial reports to Terminal (ANSI/Rich), JSON, CSV, and modern HTML.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.models import DuplicateGroup, PartialIssue


def export_json(
    duplicates: List[DuplicateGroup],
    partials: List[PartialIssue],
    output_path: str,
    extra_meta: Optional[Dict[str, Any]] = None
) -> None:
    """Exports findings to structured JSON."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "metadata": extra_meta or {},
        "summary": {
            "duplicate_groups_count": len(duplicates),
            "partial_issues_count": len(partials),
        },
        "duplicates": [d.to_dict() for d in duplicates],
        "partials": [p.to_dict() for p in partials],
    }
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_csv(duplicates: List[DuplicateGroup], output_path: str) -> None:
    """Exports duplicate candidates to CSV for spreadsheet review."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Group ID", "Target Type", "Title", "Sub Title", "Category",
            "Item Name", "Group/Scanlator", "Pages", "Path", "Is Recommended Keeper"
        ])
        for g in duplicates:
            rec_path = g.recommended_keep_path
            for it in g.items:
                is_keeper = (it.get("file_path") == rec_path or it.get("raw_name") == rec_path)
                writer.writerow([
                    g.group_id,
                    g.target_type,
                    g.title,
                    g.sub_title,
                    g.category.value if hasattr(g.category, 'value') else str(g.category),
                    it.get("raw_name") or it.get("work_name", ""),
                    it.get("scanlator_group") or it.get("scanlator", ""),
                    it.get("page_count", 0),
                    it.get("file_path", ""),
                    "YES" if is_keeper else "NO"
                ])


def export_terminal(
    duplicates: List[DuplicateGroup],
    partials: List[PartialIssue],
    total_scanned: int = 0
) -> None:
    """Prints a clear, formatted summary to standard output."""
    print("=" * 80)
    print("           MANGA & DOUJINSHI DEDUPLICATION REPORT SUMMARY           ")
    print("=" * 80)
    print(f"[*] Total Items Scanned       : {total_scanned}")
    print(f"[*] Duplicate Groups Detected : {len(duplicates)}")
    print(f"[*] Partial / Incomplete Flags: {len(partials)}")
    print("-" * 80)

    if duplicates:
        print("\n--- SAMPLE DUPLICATE GROUPS ---")
        for i, g in enumerate(duplicates[:6], 1):
            cat_name = g.category.value if hasattr(g.category, 'value') else str(g.category)
            print(f"\n[{i}] {g.title} ({g.sub_title}) [{cat_name}]")
            print(f"    Recommendation: {g.recommendation}")
            for it in g.items:
                name = it.get("raw_name") or it.get("work_name", "")
                group = it.get("scanlator_group") or it.get("scanlator", "Unknown")
                path = it.get("file_path", "")
                is_keeper = (path == g.recommended_keep_path or name == g.recommended_keep_path)
                badge = "[KEEP]" if is_keeper else "[DUPLICATE]"
                print(f"    {badge:<11} {name} (Group: {group})")

    if partials:
        print("\n--- SAMPLE PARTIAL / INCOMPLETE ISSUES ---")
        for i, p in enumerate(partials[:6], 1):
            print(f"\n[{i}] {p.series_name} [{p.issue_type}]")
            print(f"    {p.description}")

    print("\n" + "=" * 80)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Manga & Doujinshi Deduplication Report</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.1); }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans">
  <div class="max-w-7xl mx-auto p-6 space-y-6">
    <!-- Header -->
    <header class="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
      <div>
        <h1 class="text-3xl font-extrabold bg-gradient-to-r from-violet-400 via-pink-400 to-cyan-400 bg-clip-text text-transparent">
          FindDuplicates Report
        </h1>
        <p class="text-slate-400 text-sm mt-1">Generated: __TIMESTAMP__</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
          Scanned: <strong class="text-violet-400">__TOTAL_SCANNED__</strong>
        </span>
        <span class="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
          Duplicate Groups: <strong class="text-pink-400">__DUPES_COUNT__</strong>
        </span>
        <span class="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
          Partials: <strong class="text-cyan-400">__PARTIALS_COUNT__</strong>
        </span>
      </div>
    </header>

    <!-- Filters & Search -->
    <div class="flex flex-wrap items-center justify-between gap-4 glass p-4 rounded-xl">
      <div class="flex items-center gap-2 flex-1 min-w-[280px]">
        <input id="searchInput" type="text" placeholder="Search series, titles, scanlator groups..."
               class="w-full bg-slate-900 border border-slate-700 px-4 py-2 rounded-lg text-sm focus:outline-none focus:border-violet-500">
      </div>
      <div class="flex items-center gap-2">
        <button onclick="setFilter('all')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white">All (__DUPES_COUNT__)</button>
        <button onclick="setFilter('manga')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300">Manga</button>
        <button onclick="setFilter('doujinshi')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300">Doujinshi</button>
        <button onclick="setFilter('partials')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300">Partials (__PARTIALS_COUNT__)</button>
      </div>
    </div>

    <!-- Cards Container -->
    <div id="resultsContainer" class="space-y-4"></div>
  </div>

  <script>
    const duplicates = __DUPES_JSON__;
    const partials = __PARTIALS_JSON__;
    let currentFilter = 'all';

    function renderCards() {
      const container = document.getElementById('resultsContainer');
      const query = document.getElementById('searchInput').value.toLowerCase();
      container.innerHTML = '';

      if (currentFilter === 'partials') {
        const filtered = partials.filter(p => !query || p.series_name.toLowerCase().includes(query) || p.description.toLowerCase().includes(query));
        if (filtered.length === 0) {
          container.innerHTML = '<div class="p-8 text-center text-slate-500">No partial chapter issues match filter.</div>';
          return;
        }
        filtered.forEach(p => {
          const el = document.createElement('div');
          el.className = 'glass p-5 rounded-xl border-l-4 border-l-cyan-500 space-y-3';
          el.innerHTML = `
            <div class="flex items-center justify-between">
              <h3 class="text-lg font-bold text-slate-100">${p.series_name}</h3>
              <span class="px-2.5 py-1 text-xs font-semibold rounded bg-cyan-950 text-cyan-300 border border-cyan-800">${p.issue_type}</span>
            </div>
            <p class="text-sm text-slate-300">${p.description}</p>
          `;
          container.appendChild(el);
        });
        return;
      }

      const filtered = duplicates.filter(g => {
        if (currentFilter === 'manga' && g.target_type !== 'manga') return false;
        if (currentFilter === 'doujinshi' && g.target_type !== 'doujinshi') return false;
        if (query) {
          const titleMatch = g.title.toLowerCase().includes(query);
          const subMatch = g.sub_title.toLowerCase().includes(query);
          const itemMatch = g.items.some(it => (it.raw_name || it.work_name || '').toLowerCase().includes(query));
          if (!titleMatch && !subMatch && !itemMatch) return false;
        }
        return true;
      });

      if (filtered.length === 0) {
        container.innerHTML = '<div class="p-8 text-center text-slate-500">No duplicate groups match filter.</div>';
        return;
      }

      filtered.forEach(g => {
        const el = document.createElement('div');
        el.className = 'glass p-5 rounded-xl space-y-4';
        
        let itemsHtml = g.items.map(it => {
          const name = it.raw_name || it.work_name || '';
          const group = it.scanlator_group || it.scanlator || 'Uncredited';
          const path = it.file_path || name;
          const isKeeper = (path === g.recommended_keep_path || name === g.recommended_keep_path);
          return `
            <div class="flex flex-col md:flex-row md:items-center justify-between p-3 rounded-lg border ${isKeeper ? 'bg-emerald-950/30 border-emerald-800/60' : 'bg-slate-900/60 border-slate-800'} text-xs gap-2">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-200">${name}</span>
                  ${isKeeper ? '<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">RECOMMENDED KEEP</span>' : ''}
                </div>
                <div class="text-slate-400 truncate max-w-2xl font-mono text-[11px]">${path}</div>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-2 py-1 rounded bg-slate-800 text-slate-300">Group: ${group}</span>
                ${it.page_count ? `<span class="px-2 py-1 rounded bg-slate-800 text-slate-300">${it.page_count} pages</span>` : ''}
              </div>
            </div>
          `;
        }).join('');

        el.innerHTML = `
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <span class="text-xs font-semibold px-2 py-0.5 rounded ${g.target_type === 'manga' ? 'bg-violet-900/50 text-violet-300 border border-violet-700' : 'bg-pink-900/50 text-pink-300 border border-pink-700'}">${g.target_type.toUpperCase()}</span>
              <h3 class="text-lg font-bold text-slate-100 inline-block ml-2">${g.title} <span class="text-slate-400 font-normal">(${g.sub_title})</span></h3>
            </div>
            <span class="text-xs text-slate-400 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">${g.category}</span>
          </div>
          <p class="text-xs text-slate-300 bg-slate-900/40 p-2.5 rounded-lg border border-slate-800/50">${g.recommendation}</p>
          <div class="space-y-2">${itemsHtml}</div>
        `;
        container.appendChild(el);
      });
    }

    function setFilter(f) {
      currentFilter = f;
      document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('bg-violet-600', 'text-white');
        btn.classList.add('bg-slate-800', 'text-slate-300');
      });
      event.target.classList.remove('bg-slate-800', 'text-slate-300');
      event.target.classList.add('bg-violet-600', 'text-white');
      renderCards();
    }

    document.getElementById('searchInput').addEventListener('input', renderCards);
    renderCards();
  </script>
</body>
</html>
"""


def export_html(
    duplicates: List[DuplicateGroup],
    partials: List[PartialIssue],
    total_scanned: int,
    output_path: str
) -> None:
    """Exports an interactive standalone HTML report."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    dupes_json = json.dumps([d.to_dict() for d in duplicates], ensure_ascii=False)
    partials_json = json.dumps([pt.to_dict() for pt in partials], ensure_ascii=False)

    html = HTML_TEMPLATE
    html = html.replace("__TIMESTAMP__", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    html = html.replace("__TOTAL_SCANNED__", str(total_scanned))
    html = html.replace("__DUPES_COUNT__", str(len(duplicates)))
    html = html.replace("__PARTIALS_COUNT__", str(len(partials)))
    html = html.replace("__DUPES_JSON__", dupes_json)
    html = html.replace("__PARTIALS_JSON__", partials_json)

    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
