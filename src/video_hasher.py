"""
Near-duplicate video fingerprints.
Eight frames are sampled from 10% to 90% of the duration and dHashed with imagehash.
Signatures are cached by path, size, and mtime so an unchanged file is not decoded again.
"""

import hashlib
import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.cache_store import video_fingerprint_dir

try:
    from PIL import Image
    import imagehash
    HAS_IMAGE_DEPS = True
except ImportError:
    HAS_IMAGE_DEPS = False

FRAME_COUNT = 8
MEAN_HAMMING_MAX = 8
FRAME_HAMMING_MAX = 12
MIN_AGREEING_FRAMES = 6


class FfmpegNotFoundError(RuntimeError):
    """ffmpeg or ffprobe is not available on PATH."""


def frame_fractions(count: int = FRAME_COUNT) -> List[float]:
    """Evenly spaced positions from 10% through 90% of the duration."""
    if count <= 1:
        return [0.5]
    span = 0.80
    return [0.10 + (span * i / (count - 1)) for i in range(count)]


def hamming_hex(left: str, right: str) -> Optional[int]:
    if not left or not right or len(left) != len(right):
        return None
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return None


def durations_compatible(left: float, right: float) -> bool:
    """Same video within about 4% or 3 seconds, whichever is larger."""
    if left <= 0 or right <= 0:
        return False
    window = max(3.0, max(left, right) * 0.04)
    return abs(left - right) <= window


def signatures_match(
    hashes_a: Sequence[str],
    hashes_b: Sequence[str],
    mean_max: int = MEAN_HAMMING_MAX,
    frame_max: int = FRAME_HAMMING_MAX,
    min_agree: int = MIN_AGREEING_FRAMES,
) -> Tuple[bool, int]:
    """
    Very similar when the mean Hamming distance is low and most frames agree.
    Returns (is_match, rounded mean distance).
    """
    distances: List[int] = []
    for left, right in zip(hashes_a, hashes_b):
        dist = hamming_hex(left, right)
        if dist is None:
            continue
        distances.append(dist)
    if len(distances) < min_agree:
        return False, 999
    agreeing = sum(1 for dist in distances if dist <= frame_max)
    mean = sum(distances) / len(distances)
    return agreeing >= min_agree and mean <= mean_max, int(round(mean))


def _cache_key(path: str, size: int, mtime: float) -> str:
    raw = f"{os_norm(path)}|{size}|{mtime:.6f}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def os_norm(path: str) -> str:
    import os
    return os.path.normcase(os.path.normpath(path))


def load_or_compute_fingerprint(
    path: str,
    size: int,
    mtime: float,
    cache_dir: Path,
    compute_fn: Callable[[], Optional[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    Return a cached fingerprint when path, size, and mtime still match.
    compute_fn is called only on a miss and must return duration, width, height, and hashes.
    """
    folder = video_fingerprint_dir(cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    cache_file = folder / f"{_cache_key(path, size, mtime)}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as handle:
                cached = json.load(handle)
            if (
                cached.get("size") == size
                and abs(float(cached.get("mtime", -1)) - float(mtime)) < 1e-4
                and os_norm(str(cached.get("path", ""))) == os_norm(path)
                and cached.get("hashes")
            ):
                cached["cache_hit"] = True
                return cached
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    computed = compute_fn()
    if not computed or not computed.get("hashes"):
        return None
    record = {
        "path": path,
        "size": size,
        "mtime": mtime,
        "duration": float(computed.get("duration") or 0),
        "width": int(computed.get("width") or 0),
        "height": int(computed.get("height") or 0),
        "hashes": list(computed.get("hashes") or []),
    }
    with open(cache_file, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    record["cache_hit"] = False
    return record


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    raise FfmpegNotFoundError(
        "ffmpeg and ffprobe are required for video similarity and were not found on PATH. "
        "Install ffmpeg, then run the scan again."
    )


def probe_video(path: str) -> Optional[Dict[str, Any]]:
    """Duration and display size from ffprobe. None when the file has no readable video stream."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return None
    streams = payload.get("streams") or []
    fmt = payload.get("format") or {}
    width = int((streams[0].get("width") if streams else 0) or 0)
    height = int((streams[0].get("height") if streams else 0) or 0)
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        return None
    return {"duration": duration, "width": width, "height": height}


def extract_frame_png(path: str, seconds: float) -> bytes:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", f"{max(0.0, seconds):.3f}",
        "-i", path,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return b""
    if proc.returncode != 0:
        return b""
    return proc.stdout or b""


def dhash_png(data: bytes) -> Optional[str]:
    if not HAS_IMAGE_DEPS or not data:
        return None
    try:
        with Image.open(BytesIO(data)) as img:
            return str(imagehash.dhash(img.convert("RGB")))
    except Exception:
        return None


def compute_video_fingerprint(path: str) -> Optional[Dict[str, Any]]:
    """Probe the file and dHash eight frames. Returns None when the file cannot be read."""
    if not HAS_IMAGE_DEPS:
        return None
    meta = probe_video(path)
    if not meta:
        return None
    duration = float(meta["duration"])
    hashes: List[str] = []
    for fraction in frame_fractions():
        png = extract_frame_png(path, duration * fraction)
        digest = dhash_png(png)
        if digest:
            hashes.append(digest)
    if len(hashes) < MIN_AGREEING_FRAMES:
        return None
    return {
        "duration": duration,
        "width": meta["width"],
        "height": meta["height"],
        "hashes": hashes,
    }


def fingerprint_item(
    item: dict,
    cache_dir: Path,
    compute_fn: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    path = item.get("file_path") or ""
    if not path:
        return None
    size = int(item.get("file_size_bytes") or 0)
    mtime = float(item.get("mtime") or 0)
    worker = compute_fn or compute_video_fingerprint

    def _compute() -> Optional[Dict[str, Any]]:
        return worker(path)

    record = load_or_compute_fingerprint(path, size, mtime, cache_dir, _compute)
    if not record:
        return None
    merged = dict(item)
    merged.update({
        "duration": record.get("duration") or 0,
        "duration_seconds": record.get("duration") or 0,
        "width": record.get("width") or 0,
        "height": record.get("height") or 0,
        "hashes": record.get("hashes") or [],
        "cache_hit": bool(record.get("cache_hit")),
    })
    width = merged["width"]
    height = merged["height"]
    merged["resolution"] = f"{width}x{height}" if width and height else ""
    return merged


def cluster_video_records(records: List[dict]) -> List[Tuple[List[dict], int]]:
    """
    Union-find over duration-compatible pairs whose frame hashes are very similar.
    Each cluster is (members, mean hamming of the closest linked pair).
    """
    usable = [rec for rec in records if rec.get("hashes") and float(rec.get("duration") or rec.get("duration_seconds") or 0) > 0]
    parent = list(range(len(usable)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        parent[find(left)] = find(right)

    pair_distance: Dict[Tuple[int, int], int] = {}
    order = sorted(range(len(usable)), key=lambda i: float(usable[i].get("duration") or usable[i].get("duration_seconds") or 0))
    for pos, left in enumerate(order):
        left_duration = float(usable[left].get("duration") or usable[left].get("duration_seconds") or 0)
        for right in order[pos + 1:]:
            right_duration = float(usable[right].get("duration") or usable[right].get("duration_seconds") or 0)
            if not durations_compatible(left_duration, right_duration):
                break
            matched, dist = signatures_match(usable[left]["hashes"], usable[right]["hashes"])
            if matched:
                union(left, right)
                pair_distance[(min(left, right), max(left, right))] = dist

    buckets: Dict[int, List[int]] = {}
    for index in range(len(usable)):
        buckets.setdefault(find(index), []).append(index)

    clusters: List[Tuple[List[dict], int]] = []
    for indexes in buckets.values():
        if len(indexes) < 2:
            continue
        distances = [
            pair_distance[(a, b)]
            for a in indexes
            for b in indexes
            if a < b and (a, b) in pair_distance
        ]
        clusters.append(([usable[i] for i in indexes], min(distances) if distances else 0))
    return clusters
