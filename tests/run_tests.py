"""
Comprehensive Test Script for New Features:
1. Option to remove Saved Reports.
2. Option to Discard generated report.
3. Creation, management, and execution of Scan Jobs with multiple paths.
4. Saved Reports listing with job name and creation timestamp.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web.app import (
    app, STATE,
    get_scan_jobs, create_scan_job, get_scan_job, update_scan_job, delete_scan_job, run_scan_job,
    list_reports, delete_report, discard_report, get_state,
    DiscardReportPayload
)
from src.web.jobs import ScanJobCreatePayload, ScanJobUpdatePayload, job_manager
from src.config import load_config
from src.models import DuplicateGroup, DuplicateCategory
from fastapi import BackgroundTasks


def run_tests():
    print("==================================================================")
    print("    FindDuplicates: Thorough Verification of All 4 Features       ")
    print("==================================================================")

    cfg = load_config()
    rep_dir = Path(cfg.get("output", {}).get("report_directory", "./reports")).resolve()
    rep_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # FEATURE 3: Create, manage, and execute Scan Jobs in new tab
    # -----------------------------------------------------------------
    print("\n[FEATURE 3] Testing Scan Jobs Management & Execution...")

    # Create new scan job with multiple paths
    job_payload = ScanJobCreatePayload(
        name="NAS Manga & Manhwa Scan",
        target_type="manga",
        paths=[
            "/sg2b/Share2sgb/Manga",
            "/sg2b/Share2sgb/Manhwa_Webtoons",
            "G:/LocalScan"
        ],
        mode="name",
        description="Weekly automated intra-series scan"
    )
    create_res = create_scan_job(job_payload)
    assert create_res["status"] == "created"
    job = create_res["job"]
    job_id = job["id"]
    assert job["name"] == "NAS Manga & Manhwa Scan"
    assert len(job["paths"]) == 3
    assert job["target_type"] == "manga"
    print(f"  ✓ Created Scan Job: ID={job_id}, Name='{job['name']}', Paths={len(job['paths'])}")

    # Verify job listed
    jobs_list = get_scan_jobs()["jobs"]
    assert any(j["id"] == job_id for j in jobs_list), "Job should be listed in get_scan_jobs"
    print(f"  ✓ Listed Scan Jobs: {len(jobs_list)} total jobs saved")

    # Update job
    update_res = update_scan_job(job_id, ScanJobUpdatePayload(
        name="NAS Manga & Manhwa Scan (Updated)",
        paths=["/sg2b/Share2sgb/Manga", "/sg2b/Share2sgb/Extra"]
    ))
    assert update_res["status"] == "updated"
    assert update_res["job"]["name"] == "NAS Manga & Manhwa Scan (Updated)"
    assert len(update_res["job"]["paths"]) == 2
    print("  ✓ Updated Scan Job with new name and modified multiple paths")

    # Execute job
    bg = BackgroundTasks()
    run_res = run_scan_job(job_id, bg)
    assert run_res["status"] == "started"
    assert run_res["job_id"] == job_id
    assert run_res["job_name"] == "NAS Manga & Manhwa Scan (Updated)"
    print("  ✓ Executed Scan Job via user-executable trigger")

    # Delete job
    del_res = delete_scan_job(job_id)
    assert del_res["status"] == "deleted"
    assert not any(j["id"] == job_id for j in get_scan_jobs()["jobs"])
    print("  ✓ Deleted Scan Job successfully")

    # -----------------------------------------------------------------
    # FEATURE 4: Display Saved Reports with Job Origin & Created Timestamp
    # -----------------------------------------------------------------
    print("\n[FEATURE 4] Testing Saved Reports with Job Origin & Creation Timestamp...")
    test_json_name = "test_custom_job_report.json"
    test_json_path = rep_dir / test_json_name
    test_html_path = rep_dir / "test_custom_job_report.html"
    test_csv_path = rep_dir / "test_custom_job_report.csv"

    sample_meta = {
        "job_name": "Doujinshi Main Archive Scan",
        "job_id": "job_custom_123",
        "created_at": "2026-11-23 21:55:00",
        "target": "doujinshi",
        "mode": "name",
        "paths": ["/media/devmon/L500/Vere NewFolder"]
    }
    sample_report = {
        "generated_at": "2026-11-23T21:55:00",
        "metadata": sample_meta,
        "summary": {
            "total_scanned": 250,
            "duplicate_groups_count": 8,
            "partial_issues_count": 0
        },
        "duplicates": [
            {
                "group_id": "grp_sample_1",
                "target_type": "doujinshi",
                "title": "Sample Circle Work",
                "sub_title": "",
                "category": "identical_name",
                "items": [],
                "recommendation": "Keep copy 1"
            }
        ],
        "partials": []
    }
    test_json_path.write_text(json.dumps(sample_report), encoding="utf-8")
    test_html_path.write_text("<html>Report</html>", encoding="utf-8")
    test_csv_path.write_text("Group ID,Target Type\ngrp_sample_1,doujinshi\n", encoding="utf-8")

    reports_data = list_reports()
    rep_list = reports_data["reports"]
    matching_reps = [r for r in rep_list if r["filename"] == test_json_name]
    assert len(matching_reps) == 1, "Report should be found in list_reports"
    rep_item = matching_reps[0]

    assert rep_item["job_name"] == "Doujinshi Main Archive Scan", f"Unexpected job_name: {rep_item['job_name']}"
    assert rep_item["created_at"] == "2026-11-23 21:55:00", f"Unexpected created_at: {rep_item['created_at']}"
    assert rep_item["duplicates_count"] == 1
    assert rep_item["has_html"] is True
    assert rep_item["has_csv"] is True
    print(f"  ✓ Saved Report listed with metadata:")
    print(f"    • Filename: {rep_item['filename']}")
    print(f"    • Job Name: '{rep_item['job_name']}'")
    print(f"    • Created:  '{rep_item['created_at']}'")
    print(f"    • Duplicates Count: {rep_item['duplicates_count']}")

    # -----------------------------------------------------------------
    # FEATURE 1: Option to remove Saved Reports
    # -----------------------------------------------------------------
    print("\n[FEATURE 1] Testing Remove Saved Reports...")
    assert test_json_path.exists()
    assert test_html_path.exists()
    assert test_csv_path.exists()

    del_report_res = delete_report(test_json_name)
    assert del_report_res["status"] == "deleted"
    deleted_files = del_report_res["deleted_files"]
    print(f"  ✓ delete_report returned status: deleted. Removed files: {deleted_files}")

    assert not test_json_path.exists(), "JSON report should be deleted from disk"
    assert not test_html_path.exists(), "Sibling HTML report should be deleted from disk"
    assert not test_csv_path.exists(), "Sibling CSV report should be deleted from disk"
    print("  ✓ Verified all associated report files (.json, .html, .csv) permanently removed from disk")

    # -----------------------------------------------------------------
    # FEATURE 2: Option to Discard generated report
    # -----------------------------------------------------------------
    print("\n[FEATURE 2] Testing Option to Discard Generated Report...")
    # Simulate a generated/loaded report active in STATE
    STATE["manga_duplicates"] = [
        DuplicateGroup(
            group_id="active_grp_1",
            target_type="manga",
            title="Generated Manga Issue",
            sub_title="Ch. 10",
            category=DuplicateCategory.EXACT_DUPLICATE,
            items=[],
            recommendation="Keep",
            recommended_keep_path="/path/to/keep/ch10.cbz"
        )
    ]
    STATE["doujinshi_duplicates"] = [
        DuplicateGroup(
            group_id="active_grp_2",
            target_type="doujinshi",
            title="Generated Doujinshi Issue",
            sub_title="",
            category=DuplicateCategory.CROSS_DIRECTORY,
            items=[],
            recommendation="Archive",
            recommended_keep_path="/path/to/keep/work.zip"
        )
    ]
    STATE["total_scanned"] = 99
    STATE["loaded_report_name"] = "generated_scan_run_report.json"
    STATE["status_message"] = "Report ready for review in Resolution Window."

    state_before = get_state()
    assert state_before["manga_duplicates_count"] == 1
    assert state_before["doujinshi_duplicates_count"] == 1
    assert state_before["total_scanned"] == 99
    assert state_before["loaded_report_name"] == "generated_scan_run_report.json"
    print(f"  ✓ Active report before discard: {state_before['loaded_report_name']} ({state_before['total_scanned']} items scanned)")

    # Execute discard
    discard_res = discard_report(DiscardReportPayload(delete_file=False))
    assert discard_res["status"] == "discarded"
    print(f"  ✓ discard_report returned status: {discard_res['status']}")

    # Verify state cleared
    state_after = get_state()
    assert state_after["manga_duplicates_count"] == 0
    assert state_after["doujinshi_duplicates_count"] == 0
    assert state_after["manga_partials_count"] == 0
    assert state_after["total_scanned"] == 0
    assert state_after["loaded_report_name"] is None
    print("  ✓ Verified Resolution Window cleared: duplicates=0, scanned=0, active report=None")

    print("\n==================================================================")
    print("    ALL 4 FEATURES VERIFIED AND PASSED SUCCESSFULLY!             ")
    print("==================================================================")


if __name__ == "__main__":
    run_tests()
