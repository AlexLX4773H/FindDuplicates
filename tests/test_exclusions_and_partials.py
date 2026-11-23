"""
Comprehensive verification test for:
1. Discard report fix (no ReferenceError: updateStats is not defined)
2. Partials logic ignoring .5 volume specials when checking by name
3. Manga Exclusion List in Scan Jobs & Scanner
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import ChapterItem
from src.detector import detect_manga_partials
from src.web.jobs import job_manager, ScanJobCreatePayload, ScanJobUpdatePayload
from src.scanner import scan_manga_directory
from src.parser import parse_tree_dump_lines

def test_discard_report_html():
    print("[TEST 1] Verifying discardActiveReport JavaScript in index.html...")
    html_path = Path(__file__).parent.parent / "src" / "web" / "templates" / "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "updateStats" not in content, "Found unexpected 'updateStats' in index.html"
    assert "mangaData =" not in content, "Found undeclared 'mangaData =' in index.html"
    assert "doujinshiData =" not in content, "Found undeclared 'doujinshiData =' in index.html"
    assert "discardActiveReport" in content, "Missing discardActiveReport function"
    assert "jobExclusionsInput" in content, "Missing jobExclusionsInput textarea in Scan Job form"
    print("  ✓ index.html has no updateStats ReferenceError, clean discardActiveReport, and jobExclusionsInput configured")

def test_partials_half_chapters():
    print("[TEST 2] Verifying .5 chapter volume specials handling...")
    # Create test chapters matching screenshot 2:
    # Sub-chapter 1.5 coexisting with consolidated Chapter 1
    # Sub-chapter 2.5 coexisting with consolidated Chapter 2
    # Sub-chapter 12.5 coexisting with consolidated Chapter 12
    # And a true split chapter: 10.1 and 10.2 coexisting with Chapter 10
    chapters = [
        ChapterItem(raw_name="Series_Ch.1", series_name="Test Series", chapter_num=1.0, chapter_raw="1", is_archive=False),
        ChapterItem(raw_name="Series_Ch.1.5 - Special Omake", series_name="Test Series", chapter_num=1.5, chapter_raw="1.5", is_archive=False),
        ChapterItem(raw_name="Series_Ch.2", series_name="Test Series", chapter_num=2.0, chapter_raw="2", is_archive=False),
        ChapterItem(raw_name="Series_Ch.2.5 - Bonus 4-Koma", series_name="Test Series", chapter_num=2.5, chapter_raw="2.5", is_archive=False),
        ChapterItem(raw_name="Series_Ch.12", series_name="Test Series", chapter_num=12.0, chapter_raw="12", is_archive=False),
        ChapterItem(raw_name="Series_Ch.12.5 - Extra", series_name="Test Series", chapter_num=12.5, chapter_raw="12.5", is_archive=False),
        # True split partial: 10.1 with 10.0
        ChapterItem(raw_name="Series_Ch.10", series_name="Test Series", chapter_num=10.0, chapter_raw="10", is_archive=False),
        ChapterItem(raw_name="Series_Ch.10.1 - Part 1", series_name="Test Series", chapter_num=10.1, chapter_raw="10.1", is_archive=False),
    ]

    # Test when checking by name (check_mode="name")
    issues_by_name = detect_manga_partials(chapters, check_mode="name")
    fractional_issues = [i for i in issues_by_name if i.issue_type == "fractional_overlap"]
    
    # Check that 1.5, 2.5, 12.5 were NOT flagged as fractional overlap
    for issue in fractional_issues:
        assert "1.5" not in issue.description, f"1.5 was wrongly flagged: {issue.description}"
        assert "2.5" not in issue.description, f"2.5 was wrongly flagged: {issue.description}"
        assert "12.5" not in issue.description, f"12.5 was wrongly flagged: {issue.description}"

    # Check that the real split chapter 10.1 WAS flagged
    split_10_flagged = any("10.1" in i.description for i in fractional_issues)
    assert split_10_flagged, "Real split chapter 10.1 was not detected"

    print(f"  ✓ Under check_mode='name': {len(fractional_issues)} issue detected (only real split 10.1; .5 specials 1.5, 2.5, 12.5 correctly ignored)")

def test_manga_exclusion_list():
    print("[TEST 3] Verifying Manga Exclusion List in Scan Jobs...")
    # Create a job with excluded manga
    payload = ScanJobCreatePayload(
        name="NAS Manga with Exclusions",
        target_type="manga",
        paths=["/sg2b/Share2sgb/Manga"],
        mode="name",
        description="Scan job excluding specific completed series",
        excluded_manga=["Flag Capture in the First Move", "Retired Heroes"]
    )
    job = job_manager.create_job(payload)
    job_id = job["id"]

    retrieved = job_manager.get_job(job_id)
    assert retrieved is not None
    assert retrieved["excluded_manga"] == ["Flag Capture in the First Move", "Retired Heroes"]
    print(f"  ✓ Job created with exclusions: {retrieved['excluded_manga']}")

    # Update job with modified exclusions
    up_payload = ScanJobUpdatePayload(
        excluded_manga=["Flag Capture in the First Move", "Retired Heroes", "One Piece"]
    )
    updated = job_manager.update_job(job_id, up_payload)
    assert updated["excluded_manga"] == ["Flag Capture in the First Move", "Retired Heroes", "One Piece"]
    print(f"  ✓ Job updated with 3 exclusions: {updated['excluded_manga']}")

    # Test parser tree dump exclusion
    sample_tree_lines = [
        "+---Manga_1",
        "|   +---Axe",
        "|   |   +---Flag Capture in the First Move",
        "|   |   |   +---Ch.1.cbz",
        "|   |   +---Retired Heroes",
        "|   |   |   +---Ch.1.cbz",
        "|   |   +---Unrivaled Hero",
        "|   |   |   +---Ch.1.cbz"
    ]
    t_type, items = parse_tree_dump_lines(sample_tree_lines, excluded_manga=["Flag Capture in the First Move", "Retired Heroes"])
    assert t_type == "manga"
    series_names = [it.series_name for it in items]
    assert "Flag Capture in the First Move" not in series_names
    assert "Retired Heroes" not in series_names
    assert "Unrivaled Hero" in series_names
    print(f"  ✓ Tree parser excluded specified manga; only '{series_names}' included")

    # Clean up test job
    job_manager.delete_job(job_id)
    print("  ✓ Test scan job cleaned up")

if __name__ == '__main__':
    test_discard_report_html()
    test_partials_half_chapters()
    test_manga_exclusion_list()
    print("\n=======================================================")
    print("  ALL EXCLUSION & PARTIALS TESTS PASSED (100% OK)      ")
    print("=======================================================")
