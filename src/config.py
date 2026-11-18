"""
Configuration and Path Normalization Module
Handles Windows drive letters, network UNC shares, and Linux/CasaOS paths.
Supports dedicated Manga and Doujinshi paths, environment variables, and defaults.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "scan_paths": [
        "/sg2b/Share2sgb/Manga",
        "/media/devmon/L500/Vere NewFolder"
    ],
    "manga_paths": [
        "/sg2b/Share2sgb/Manga"
    ],
    "doujinshi_paths": [
        "/media/devmon/L500/Vere NewFolder"
    ],
    "detection": {
        "detect_fractional_chapters": True,
        "detect_incomplete_pages": True,
        "min_page_ratio": 0.60,
        "partial_keywords": ["incomplete", "sample", "preview", "partial", "missing"],
        "supported_archives": [".cbz", ".zip", ".cbr", ".rar"],
        "supported_images": [".jpg", ".jpeg", ".png", ".webp", ".avif"],
    },
    "image_inspection": {
        "enabled": True,
        "hash_algorithm": "dhash",
        "hash_size": 8,
        "hamming_threshold": 6,
        "cache_directory": "./cache"
    },
    "output": {
        "report_directory": "./reports",
        "formats": ["terminal", "html", "json", "csv"],
    },
}


def normalize_path(raw_path: str) -> Path:
    """
    Normalizes path whether provided with Windows or Linux slashes.
    Expands user home ~ and environment variables.
    """
    cleaned = raw_path.strip().strip("'\"")
    expanded = os.path.expanduser(os.path.expandvars(cleaned))
    return Path(expanded).resolve()


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Loads configuration from YAML file, with fallback to environment variables
    and defaults.
    """
    config = DEFAULT_CONFIG.copy()

    # Fallback to config.example.yaml if config.yaml does not exist
    actual_path = config_path if (os.path.exists(config_path) and os.path.isfile(config_path)) else ("config.example.yaml" if (os.path.exists("config.example.yaml") and os.path.isfile("config.example.yaml")) else None)

    if actual_path and os.path.exists(actual_path) and os.path.isfile(actual_path):
        try:
            with open(actual_path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
                for key, val in user_cfg.items():
                    if isinstance(val, dict) and key in config:
                        config[key].update(val)
                    else:
                        config[key] = val
        except Exception as e:
            print(f"[Warning] Failed to load config from {actual_path}: {e}. Using defaults.")

    # Override from environment variables if present (useful for Docker & CasaOS)
    if "SCAN_PATHS" in os.environ:
        paths = [p.strip() for p in os.environ["SCAN_PATHS"].split(",") if p.strip()]
        config["scan_paths"] = paths

    if "MANGA_SCAN_PATH" in os.environ:
        m_paths = [p.strip() for p in os.environ["MANGA_SCAN_PATH"].split(",") if p.strip()]
        config["manga_paths"] = m_paths

    if "DOUJINSHI_SCAN_PATH" in os.environ:
        d_paths = [p.strip() for p in os.environ["DOUJINSHI_SCAN_PATH"].split(",") if p.strip()]
        config["doujinshi_paths"] = d_paths

    if "OUTPUT_DIR" in os.environ:
        config["output"]["report_directory"] = os.environ["OUTPUT_DIR"]

    if "DETECT_PARTIALS" in os.environ:
        config["detection"]["detect_fractional_chapters"] = os.environ["DETECT_PARTIALS"].lower() in ("true", "1", "yes")

    # Normalize scan paths
    normalized_paths: List[Path] = []
    for p in config.get("scan_paths", []):
        normalized_paths.append(normalize_path(p))
    config["normalized_scan_paths"] = normalized_paths

    # Normalize manga paths
    m_norm: List[Path] = []
    for p in config.get("manga_paths", []):
        m_norm.append(normalize_path(p))
    config["normalized_manga_paths"] = m_norm

    # Normalize doujinshi paths
    d_norm: List[Path] = []
    for p in config.get("doujinshi_paths", []):
        d_norm.append(normalize_path(p))
    config["normalized_doujinshi_paths"] = d_norm

    return config
