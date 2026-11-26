"""Visual scans keep only chapters whose story pages match."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

from src.detector import detect_exact_hash_duplicates, detect_visual_duplicates, retain_visual_matches
from src.image_hasher import verify_chapter_similarity
from src.models import DuplicateCategory, DuplicateGroup


def _chapter(folder: Path, color, marks):
    folder.mkdir(parents=True)
    for i, mark in enumerate(marks):
        img = Image.new("RGB", (160, 220), color)
        draw = ImageDraw.Draw(img)
        draw.rectangle(mark, fill=(255, 255, 255))
        img.save(folder / f"{i:03d}.jpg", quality=95)


def test_visual_scan_drops_name_only_collisions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        same_a = root / "GroupA_Ch.1"
        same_b = root / "GroupB_Ch.1"
        other = root / "GroupC_Ch.1"
        # Shared story pages. Different first page, which is the usual credits card.
        story = [(20, 40, 80, 140), (30, 80, 120, 180), (10, 20, 70, 90), (40, 100, 140, 200)]
        _chapter(same_a, (30, 30, 30), [(0, 0, 160, 40)] + story)
        _chapter(same_b, (30, 30, 30), [(0, 0, 40, 220)] + story)
        _chapter(other, (180, 40, 40), [(i * 10, i * 15, 150, 200) for i in range(5)])

        match, dist, expl = verify_chapter_similarity(str(same_a), str(same_b))
        assert match, expl
        assert dist <= 12

        mismatch, _, expl_bad = verify_chapter_similarity(str(same_a), str(other))
        assert not mismatch, expl_bad

        group = DuplicateGroup(
            group_id="manga_test",
            target_type="manga",
            title="Example",
            sub_title="Chapter 1",
            category=DuplicateCategory.ALTERNATIVE_SCANLATION,
            items=[
                {"raw_name": "GroupA", "file_path": str(same_a), "page_count": 5},
                {"raw_name": "GroupB", "file_path": str(same_b), "page_count": 5},
                {"raw_name": "GroupC", "file_path": str(other), "page_count": 5},
            ],
            recommendation="Multiple scanlation groups found.",
            recommended_keep_path=str(same_a),
        )
        kept = retain_visual_matches([group])
        assert len(kept) == 1
        names = {it["raw_name"] for it in kept[0].items}
        assert names == {"GroupA", "GroupB"}
        assert "Visual match verified" in kept[0].recommendation
        assert kept[0].hamming_distance is not None and kept[0].hamming_distance <= 12


def test_visual_similarity_ignores_chapter_names():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        story = [(20, 40, 80, 140), (30, 80, 120, 180), (10, 20, 70, 90), (40, 100, 140, 200)]
        same_a = root / "not_a_chapter_name"
        same_b = root / "completely_different_folder"
        other = root / "different_artwork"
        _chapter(same_a, (30, 30, 30), [(0, 0, 160, 40)] + story)
        _chapter(same_b, (30, 30, 30), [(0, 0, 40, 220)] + story)
        _chapter(other, (180, 40, 40), [(i * 10, i * 15, 150, 200) for i in range(5)])

        items = [
            {"raw_name": "not-chapter-10", "series_name": "Example", "chapter_num": None, "file_path": str(same_a), "page_count": 5, "file_size_bytes": 1},
            {"raw_name": "misc_extra", "series_name": "Example", "chapter_num": 99, "file_path": str(same_b), "page_count": 5, "file_size_bytes": 2},
            {"raw_name": "other-art", "series_name": "Example", "chapter_num": 1, "file_path": str(other), "page_count": 5, "file_size_bytes": 1},
        ]
        groups = detect_visual_duplicates(items, target_type="manga")
        assert len(groups) == 1, groups
        names = {it["raw_name"] for it in groups[0].items}
        assert names == {"not-chapter-10", "misc_extra"}
        assert groups[0].category == DuplicateCategory.VISUAL_MATCH
        assert "Hamming distance" in groups[0].recommendation


def test_exact_hash_rejects_reencoded_images():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        marks = [(20, 40, 80, 140), (30, 80, 120, 180), (10, 20, 70, 90)]
        source = root / "source"
        _chapter(source, (40, 90, 140), marks)
        identical = root / "identical_copy"
        shutil.copytree(source, identical)
        reencoded = root / "reencoded"
        reencoded.mkdir()
        for image_path in source.glob("*.jpg"):
            with Image.open(image_path) as img:
                img.save(reencoded / image_path.name, quality=35)

        items = [
            {"raw_name": "copy-a", "series_name": "Example", "file_path": str(source), "page_count": 3, "file_size_bytes": 100},
            {"raw_name": "copy-b", "series_name": "Somewhere Else", "file_path": str(identical), "page_count": 3, "file_size_bytes": 100},
            {"raw_name": "softer-jpeg", "series_name": "Example", "file_path": str(reencoded), "page_count": 3, "file_size_bytes": 40},
        ]
        exact = detect_exact_hash_duplicates(items, target_type="manga")
        assert len(exact) == 1, exact
        exact_names = {it["raw_name"] for it in exact[0].items}
        assert exact_names == {"copy-a", "copy-b"}
        assert "Byte-identical" in exact[0].recommendation

        visual = detect_visual_duplicates(items, target_type="manga")
        assert len(visual) == 1, visual
        visual_names = {it["raw_name"] for it in visual[0].items}
        assert visual_names == {"copy-a", "softer-jpeg"}


if __name__ == "__main__":
    test_visual_scan_drops_name_only_collisions()
    test_visual_similarity_ignores_chapter_names()
    test_exact_hash_rejects_reencoded_images()
    print("ok")
