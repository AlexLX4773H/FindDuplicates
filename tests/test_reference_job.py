"""Reference jobs keep the exact copy that shares the reference relative path."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image

from src.detector import detect_reference_duplicates
from src.scanner import scan_doujinshi_directory
from src.web.jobs import validate_reference_directories


def _seed_image(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (48, 48), (12, 34, 56))
    image.save(path, quality=95)


def _copy_work(src: Path, dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest_dir / src.name)


def test_matching_relative_path_is_the_keeper():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        canonical = root / "reference" / "Circle" / "Title" / "001.jpg"
        _seed_image(canonical)
        library = root / "library" / "Circle" / "Title"
        staging = root / "staging" / "000 NEW" / "Title"
        _copy_work(canonical, library)
        _copy_work(canonical, staging)

        compare_roots = [root / "library", root / "staging"]
        reference_roots = [root / "reference"]
        compare_items = []
        for scan_root in compare_roots:
            compare_items.extend(scan_doujinshi_directory(scan_root))
        reference_items = scan_doujinshi_directory(reference_roots[0])

        groups = detect_reference_duplicates(
            compare_items,
            reference_items,
            compare_roots=compare_roots,
            reference_roots=reference_roots,
        )
        assert len(groups) == 1
        group = groups[0]
        assert group.position_matched is True
        assert Path(group.recommended_keep_path).resolve() == library.resolve()
        archived = {
            Path(item["file_path"]).resolve()
            for item in group.items
            if Path(item["file_path"]).resolve() != library.resolve()
        }
        assert staging.resolve() in archived
        assert all(item.get("directory_role") == "compare" for item in group.items)
        assert {item["relative_path"] for item in group.items} == {"Circle/Title", "000 NEW/Title"}
        assert all(Path(item["file_path"]).resolve() != canonical.parent.resolve() for item in group.items)
        assert group.to_dict()["position_matched"] is True


def test_no_shared_relative_path_stays_unresolved():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        canonical = root / "reference" / "Circle" / "Title" / "001.jpg"
        _seed_image(canonical)
        other = root / "library" / "Other" / "Title"
        temp = root / "staging" / "Temp" / "Title"
        _copy_work(canonical, other)
        _copy_work(canonical, temp)

        compare_roots = [root / "library", root / "staging"]
        reference_roots = [root / "reference"]
        compare_items = []
        for scan_root in compare_roots:
            compare_items.extend(scan_doujinshi_directory(scan_root))
        reference_items = scan_doujinshi_directory(reference_roots[0])

        groups = detect_reference_duplicates(
            compare_items,
            reference_items,
            compare_roots=compare_roots,
            reference_roots=reference_roots,
        )
        assert len(groups) == 1
        group = groups[0]
        assert group.position_matched is False
        assert group.recommended_keep_path == ""
        assert "Review manually" in group.recommendation


def test_several_position_matches_keep_the_largest():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        canonical = root / "reference" / "Circle" / "Title" / "001.jpg"
        _seed_image(canonical)
        small = root / "library" / "Circle" / "Title"
        large = root / "mirror" / "Circle" / "Title"
        extra = root / "staging" / "Temp" / "Title"
        _copy_work(canonical, small)
        _copy_work(canonical, large)
        _copy_work(canonical, extra)

        compare_roots = [root / "library", root / "mirror", root / "staging"]
        items = [
            {"raw_name": "Title", "work_name": "Title", "file_path": str(small), "page_count": 1, "file_size_bytes": 10},
            {"raw_name": "Title", "work_name": "Title", "file_path": str(large), "page_count": 4, "file_size_bytes": 50},
            {"raw_name": "Title", "work_name": "Title", "file_path": str(extra), "page_count": 9, "file_size_bytes": 100},
        ]
        reference_items = [{"raw_name": "Title", "work_name": "Title", "file_path": str(canonical.parent), "page_count": 1, "file_size_bytes": 10}]
        groups = detect_reference_duplicates(
            items,
            reference_items,
            compare_roots=compare_roots,
            reference_roots=[root / "reference"],
        )
        assert len(groups) == 1
        assert groups[0].position_matched is True
        assert Path(groups[0].recommended_keep_path).resolve() == large.resolve()


def test_reference_job_validation():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        compare = root / "library"
        reference = root / "canonical"
        nested = compare / "nested"
        compare.mkdir()
        reference.mkdir()
        nested.mkdir()

        assert validate_reference_directories("manga", "name", [str(compare)], []) == []
        cleaned = validate_reference_directories("doujinshi", "reference", [str(compare)], [str(reference)])
        assert cleaned == [str(reference)]

        try:
            validate_reference_directories("manga", "reference", [str(compare)], [str(reference)])
            raise AssertionError("manga reference job should be rejected")
        except ValueError as exc:
            assert "Doujinshi" in str(exc)

        try:
            validate_reference_directories("doujinshi", "reference", [str(compare)], [])
            raise AssertionError("missing reference directory should be rejected")
        except ValueError as exc:
            assert "reference directory" in str(exc)

        try:
            validate_reference_directories("doujinshi", "reference", [str(compare)], [str(compare)])
            raise AssertionError("identical directories should be rejected")
        except ValueError as exc:
            assert "overlap" in str(exc)

        try:
            validate_reference_directories("doujinshi", "reference", [str(compare)], [str(nested)])
            raise AssertionError("nested reference directory should be rejected")
        except ValueError as exc:
            assert "overlap" in str(exc)
