"""
Visual & Perceptual Image Hashing Engine
Computes dHash / pHash for chapter pages and doujinshi covers directly from
loose image folders or streamed from .cbz / .zip archive headers without full extraction.
"""

import os
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

try:
    from PIL import Image
    import imagehash
    HAS_IMAGE_DEPS = True
except ImportError:
    HAS_IMAGE_DEPS = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp"}


def is_image_file(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS and not Path(name).name.startswith("._")


def get_images_in_folder(folder_path: Path) -> List[Path]:
    """Lists sorted image paths inside a folder."""
    images = []
    try:
        if folder_path.is_dir():
            with os.scandir(folder_path) as it:
                for entry in it:
                    if entry.is_file() and is_image_file(entry.name):
                        images.append(Path(entry.path))
    except (PermissionError, OSError):
        pass
    return sorted(images, key=lambda p: p.name.lower())


def get_images_in_archive(archive_path: Path) -> List[str]:
    """Lists sorted internal image filenames inside a zip/cbz archive."""
    images = []
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            for name in z.namelist():
                if is_image_file(name) and not name.startswith('__MACOSX'):
                    images.append(name)
    except (zipfile.BadZipFile, OSError, PermissionError):
        pass
    return sorted(images, key=lambda n: n.lower())


def load_image_bytes(item_path: str, sub_index: int = 0) -> Optional[Tuple[bytes, Tuple[int, int]]]:
    """
    Retrieves raw image bytes and dimensions for an image at sub_index (e.g. 0 for cover).
    Works for both folder of images and .zip/.cbz archives.
    """
    p = Path(item_path)
    if not p.exists():
        return None

    if p.is_file() and p.suffix.lower() in {".cbz", ".zip"}:
        try:
            with zipfile.ZipFile(p, 'r') as z:
                img_names = [n for n in z.namelist() if is_image_file(n) and not n.startswith('__MACOSX')]
                img_names = sorted(img_names, key=lambda n: n.lower())
                if img_names and sub_index < len(img_names):
                    target_name = img_names[sub_index]
                    data = z.read(target_name)
                    if HAS_IMAGE_DEPS:
                        with Image.open(BytesIO(data)) as img:
                            dim = img.size
                    else:
                        dim = (0, 0)
                    return data, dim
        except Exception:
            return None

    elif p.is_dir():
        # Check if direct images or child 'chapter' folder
        imgs = get_images_in_folder(p)
        if not imgs:
            for child in p.iterdir():
                if child.is_dir():
                    sub_imgs = get_images_in_folder(child)
                    if sub_imgs:
                        imgs = sub_imgs
                        break

        if imgs and sub_index < len(imgs):
            try:
                target_img = imgs[sub_index]
                with open(target_img, 'rb') as f:
                    data = f.read()
                if HAS_IMAGE_DEPS:
                    with Image.open(BytesIO(data)) as img:
                        dim = img.size
                else:
                    dim = (0, 0)
                return data, dim
            except Exception:
                return None

    return None


def compute_perceptual_hash(item_path: str, page_index: int = 0, hash_type: str = "dhash") -> Optional[str]:
    """
    Computes perceptual hash string for an image page inside folder or archive.
    """
    if not HAS_IMAGE_DEPS:
        return None

    res = load_image_bytes(item_path, page_index)
    if not res:
        return None

    data, _ = res
    try:
        with Image.open(BytesIO(data)) as img:
            # Convert to RGB to avoid alpha/palette issues
            img_rgb = img.convert('RGB')
            if hash_type.lower() == "phash":
                h = imagehash.phash(img_rgb)
            else:
                h = imagehash.dhash(img_rgb)
            return str(h)
    except Exception:
        return None


def compute_hamming_distance(hash1_str: str, hash2_str: str) -> Optional[int]:
    """Calculates Hamming distance between two hex hash strings."""
    if not HAS_IMAGE_DEPS or not hash1_str or not hash2_str:
        return None
    try:
        h1 = imagehash.hex_to_hash(hash1_str)
        h2 = imagehash.hex_to_hash(hash2_str)
        return int(h1 - h2)
    except Exception:
        return None


def count_images(item_path: str) -> int:
    """How many page images a chapter folder or archive contains."""
    p = Path(item_path)
    if not p.exists():
        return 0
    if p.is_file() and p.suffix.lower() in {".cbz", ".zip"}:
        return len(get_images_in_archive(p))
    if p.is_dir():
        imgs = get_images_in_folder(p)
        if imgs:
            return len(imgs)
        try:
            for child in p.iterdir():
                if child.is_dir():
                    sub = get_images_in_folder(child)
                    if sub:
                        return len(sub)
        except (PermissionError, OSError):
            return 0
    return 0


def sample_page_indices(page_count: int) -> List[int]:
    """
    Pages used to decide whether two releases are the same chapter.
    The first file is often a credits or title card that differs by scanlator,
    so once a chapter has a few pages we compare the next page, the middle, and the last.
    """
    if page_count <= 0:
        return []
    if page_count == 1:
        return [0]
    if page_count == 2:
        return [0, 1]
    first = 1 if page_count >= 4 else 0
    return sorted({first, page_count // 2, page_count - 1})


def verify_chapter_similarity(path_a: str, path_b: str, threshold: int = 12) -> Tuple[bool, int, str]:
    """
    Compare story pages of two chapters.
    Distance <= threshold (default 12) is the same artwork, including rescans.
    A credits page is ignored when other pages exist, so a different title card
    does not hide a matching chapter.
    Returns: (is_duplicate, hamming_distance, explanation)
    """
    if not HAS_IMAGE_DEPS:
        return False, 999, "imagehash/Pillow libraries not installed"

    samples_a = sample_page_indices(count_images(path_a))
    samples_b = sample_page_indices(count_images(path_b))
    if not samples_a or not samples_b:
        return False, 999, "Could not extract page images for visual comparison"

    judged: List[Tuple[int, int]] = []
    for index_a, index_b in zip(samples_a, samples_b):
        hash_a = compute_perceptual_hash(path_a, index_a)
        hash_b = compute_perceptual_hash(path_b, index_b)
        if not hash_a or not hash_b:
            continue
        dist = compute_hamming_distance(hash_a, hash_b)
        if dist is None:
            continue
        judged.append((index_a, dist))

    if not judged:
        return False, 999, "Could not extract page images for visual comparison"

    story = [dist for index, dist in judged if index != 0] or [dist for _, dist in judged]
    story_sorted = sorted(story)
    median = story_sorted[len(story_sorted) // 2]
    is_match = median <= threshold
    if is_match:
        return True, median, f"Visual match verified (Hamming distance: {median})"
    return False, median, f"Visual mismatch (Hamming distance: {median} > {threshold})"


def cluster_visually_matching_items(items: List[dict], threshold: int = 12) -> Tuple[List[Tuple[List[dict], int, str]], str]:
    """
    Split a name-matched group into clusters that share artwork.
    Status is "matched", "different", or "unreadable".
    """
    usable = [it for it in items if it.get("file_path")]
    if len(usable) < 2:
        return [], "unreadable"

    parent = list(range(len(usable)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pair_distance: Dict[Tuple[int, int], int] = {}
    compared = 0
    unreadable = 0
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            match, dist, expl = verify_chapter_similarity(
                usable[i]["file_path"], usable[j]["file_path"], threshold
            )
            compared += 1
            if "Could not extract" in expl or "not installed" in expl:
                unreadable += 1
                continue
            if match:
                parent[find(i)] = find(j)
                pair_distance[(i, j)] = dist

    buckets: Dict[int, List[int]] = {}
    for i in range(len(usable)):
        buckets.setdefault(find(i), []).append(i)

    clusters: List[Tuple[List[dict], int, str]] = []
    for indexes in buckets.values():
        if len(indexes) < 2:
            continue
        distances = [
            pair_distance[(a, b)]
            for a in indexes
            for b in indexes
            if a < b and (a, b) in pair_distance
        ]
        dist = min(distances) if distances else 0
        clusters.append((
            [usable[i] for i in indexes],
            dist,
            f"Visual match verified (Hamming distance: {dist})",
        ))

    if clusters:
        return clusters, "matched"
    if compared > 0 and unreadable == compared:
        return [], "unreadable"
    return [], "different"
