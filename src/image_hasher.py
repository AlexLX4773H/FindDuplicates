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


def verify_chapter_similarity(path_a: str, path_b: str, threshold: int = 6) -> Tuple[bool, int, str]:
    """
    Compares Page 1 (cover) and Mid-Page of two chapters to definitively verify identical artwork.
    Returns: (is_duplicate, hamming_distance, explanation)
    """
    if not HAS_IMAGE_DEPS:
        return False, 999, "imagehash/Pillow libraries not installed"

    hash_a_cov = compute_perceptual_hash(path_a, 0)
    hash_b_cov = compute_perceptual_hash(path_b, 0)

    if not hash_a_cov or not hash_b_cov:
        return False, 999, "Could not extract cover images for visual comparison"

    dist_cov = compute_hamming_distance(hash_a_cov, hash_b_cov) or 999

    if dist_cov <= threshold:
        return True, dist_cov, f"Visual match verified (Hamming distance: {dist_cov})"
    else:
        return False, dist_cov, f"Visual mismatch (Hamming distance: {dist_cov} > {threshold})"
