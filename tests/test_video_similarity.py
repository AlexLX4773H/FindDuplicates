"""Near-duplicate video clustering, fingerprint cache, and cache clearing."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.cache_store import cache_summary, clear_cache
from src.detector import detect_video_duplicates
from src.video_hasher import (
    cluster_video_records,
    durations_compatible,
    load_or_compute_fingerprint,
    signatures_match,
)
from src.video_scanner import scan_video_tree


SAME = ["0" * 16] * 8
FAR = ["f" * 16] * 8


def _record(name, duration, hashes, width=1920, height=1080, size=100):
    return {
        "raw_name": name,
        "file_path": f"/library/{name}",
        "file_size_bytes": size,
        "duration": duration,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "hashes": list(hashes),
        "resolution": f"{width}x{height}",
    }


def test_identical_signatures_group():
    groups = cluster_video_records([
        _record("a.mp4", 100, SAME, size=10),
        _record("b.mkv", 102, SAME, size=50, width=1280, height=720),
        _record("other.mp4", 100, FAR, size=80),
    ])
    assert len(groups) == 1
    members, dist = groups[0]
    assert dist == 0
    names = {item["raw_name"] for item in members}
    assert names == {"a.mp4", "b.mkv"}


def test_distant_signatures_do_not_group():
    assert signatures_match(SAME, FAR)[0] is False
    groups = cluster_video_records([
        _record("a.mp4", 100, SAME),
        _record("b.mp4", 100, FAR),
    ])
    assert groups == []


def test_duration_mismatch_stays_apart():
    assert durations_compatible(100, 102)
    assert not durations_compatible(100, 200)
    groups = cluster_video_records([
        _record("short.mp4", 100, SAME),
        _record("long.mkv", 200, SAME),
    ])
    assert groups == []


def test_cache_reused_until_mtime_changes():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"duration": 12.0, "width": 640, "height": 360, "hashes": list(SAME)}

    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        first = load_or_compute_fingerprint("/videos/clip.mp4", 20, 1.0, cache, compute)
        second = load_or_compute_fingerprint("/videos/clip.mp4", 20, 1.0, cache, compute)
        assert first is not None and second is not None
        assert first["cache_hit"] is False
        assert second["cache_hit"] is True
        assert calls["n"] == 1
        third = load_or_compute_fingerprint("/videos/clip.mp4", 20, 2.0, cache, compute)
        assert third["cache_hit"] is False
        assert calls["n"] == 2


def test_clear_cache_removes_only_cache_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache = root / "cache"
        reports = root / "reports"
        cache.mkdir()
        reports.mkdir()
        fingerprint = cache / "video_fingerprints"
        fingerprint.mkdir()
        (fingerprint / "abc.json").write_text("{}", encoding="utf-8")
        (cache / "loose.txt").write_text("x", encoding="utf-8")
        (reports / "latest_report.json").write_text("[]", encoding="utf-8")

        before = cache_summary(cache)
        assert before["file_count"] == 2
        result = clear_cache(cache)
        assert result["deleted_files"] == 2
        assert cache.exists()
        assert cache_summary(cache)["file_count"] == 0
        assert (reports / "latest_report.json").exists()


def test_scanner_walks_nested_tree():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested = root / "season" / "extras"
        nested.mkdir(parents=True)
        (nested / "show.mkv").write_bytes(b"mkv")
        (root / "movie.mp4").write_bytes(b"mp4")
        (root / "notes.txt").write_text("no", encoding="utf-8")
        (nested / "cover.jpg").write_bytes(b"jpg")
        found = scan_video_tree(root)
        names = sorted(item["raw_name"] for item in found)
        assert names == ["movie.mp4", "show.mkv"]


def test_video_job_mode_is_forced():
    from src.web.jobs import normalize_job_mode
    assert normalize_job_mode("video", "name") == ("video", "similar")
    try:
        normalize_job_mode("manga", "similar")
        raise AssertionError("similar mode should be rejected for manga")
    except ValueError:
        pass


def test_detect_video_duplicates_uses_injected_fingerprints():
    """Group two files from injected signatures without calling ffmpeg."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        left = root / "alpha.mp4"
        right = root / "beta.mkv"
        left.write_bytes(b"a")
        right.write_bytes(b"b")
        items = scan_video_tree(root)

        def fake_compute(path):
            return {"duration": 30.0, "width": 1920 if path.endswith(".mp4") else 1280, "height": 1080 if path.endswith(".mp4") else 720, "hashes": list(SAME)}

        from src import video_hasher
        original = video_hasher.compute_video_fingerprint
        original_ensure = video_hasher.ensure_ffmpeg
        video_hasher.compute_video_fingerprint = fake_compute
        video_hasher.ensure_ffmpeg = lambda: None
        try:
            groups = detect_video_duplicates(items, cache_dir=root / "cache")
        finally:
            video_hasher.compute_video_fingerprint = original
            video_hasher.ensure_ffmpeg = original_ensure

        assert len(groups) == 1
        assert groups[0].target_type == "video"
        assert groups[0].recommended_keep_path.endswith("alpha.mp4")
        assert all("hashes" not in item for item in groups[0].items)
        cached = list((root / "cache" / "video_fingerprints").glob("*.json"))
        assert len(cached) == 2
        payload = json.loads(cached[0].read_text(encoding="utf-8"))
        assert payload["hashes"]


def test_ffmpeg_roundtrip_when_available():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("  - skipped ffmpeg integration (ffmpeg not installed)")
        return
    from src.video_hasher import compute_video_fingerprint

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clip = root / "pattern.mp4"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=160x120:rate=8:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(clip),
        ]
        proc = __import__("subprocess").run(cmd, capture_output=True)
        if proc.returncode != 0 or not clip.exists():
            print("  - skipped ffmpeg integration (could not encode a sample)")
            return
        copy = root / "nested" / "pattern-copy.mp4"
        copy.parent.mkdir()
        shutil.copy(clip, copy)
        left = compute_video_fingerprint(str(clip))
        right = compute_video_fingerprint(str(copy))
        assert left and right
        matched, _dist = signatures_match(left["hashes"], right["hashes"])
        assert matched
