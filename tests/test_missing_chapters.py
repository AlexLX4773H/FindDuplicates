"""Missing-chapter jobs list gaps and do not choose a copy to keep."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.detector import detect_missing_chapters
from src.models import ChapterItem
from src.web.jobs import normalize_job_mode


def _chapter(series, number, name=None):
    label = name or (f"Chapter {number:g}" if number is not None else "Extra")
    return ChapterItem(
        raw_name=label,
        series_name=series,
        chapter_num=number,
        chapter_raw="" if number is None else f"{number:g}",
    )


def test_missing_chapters_are_the_gaps_between_first_and_last():
    chapters = [
        _chapter("Tower", 1),
        _chapter("Tower", 2),
        _chapter("Tower", 2.5),
        _chapter("Tower", 4),
        _chapter("Tower", 7),
        _chapter("Tower", 8),
        _chapter("Tower", 9),
        _chapter("Tower", 15),
        _chapter("Side Story", 50),
        _chapter("Side Story", 51),
        _chapter("Side Story", 53),
        _chapter("Complete", 1),
        _chapter("Complete", 2),
        _chapter("Complete", 3),
        _chapter("Only Extra", 1.5),
        _chapter("Only Extra", 2.5),
        _chapter("Single", 4),
    ]
    issues = detect_missing_chapters(chapters)
    by_series = {issue.series_name: issue for issue in issues}

    assert set(by_series) == {"Tower", "Side Story"}
    assert by_series["Tower"].issue_type == "missing_chapters"
    assert by_series["Tower"].description == "Missing chapters: 3, 5–6, 10–14"
    assert by_series["Tower"].affected_items == []
    assert by_series["Side Story"].description == "Missing chapters: 52"
    assert "Complete" not in by_series
    assert "Only Extra" not in by_series
    assert "Single" not in by_series


def test_missing_mode_is_manga_only():
    assert normalize_job_mode("manga", "missing") == ("manga", "missing")
    for target in ("doujinshi", "video", "all"):
        try:
            normalize_job_mode(target, "missing")
        except ValueError as exc:
            assert "Manga" in str(exc)
        else:
            raise AssertionError(f"{target} should reject missing chapters mode")


if __name__ == "__main__":
    test_missing_chapters_are_the_gaps_between_first_and_last()
    test_missing_mode_is_manga_only()
    print("ok")
