"""Visual scans keep only chapters whose story pages match."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

from src.detector import retain_visual_matches
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


if __name__ == "__main__":
    test_visual_scan_drops_name_only_collisions()
    print("ok")
