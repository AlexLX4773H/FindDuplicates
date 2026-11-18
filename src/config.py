"""
Configuration and Path Normalization Module
Handles Windows drive letters, network UNC shares, and Linux/CasaOS paths.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "scan_paths": [],
    "detection": {
        "detect_fractional_chapters": True,
        "detect_incomplete_pages": True,
        "min_page_ratio": 0.60,
        "partial_keywords": ["incomplete", "sample", "preview", "partial", "missing"],
        "supported_archives": [".cbz", ".zip", ".cbr", ".rar"],
        "supported_images": [".jpg", ".jpeg", ".png", ".webp", ".avif"],
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
    expanded = os.path.expanduser(os.path.expandvars(raw_path.strip()))
    return Path(expanded).resolve()

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Loads configuration from YAML file, with fallback to environment variables
    and defaults.
    """
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
                # Deep merge top-level keys
                for key, val in user_cfg.items():
                    if isinstance(val, dict) and key in config:
                        config[key].update(val)
                    else:
                        config[key] = val
        except Exception as e:
            print(f"[Warning] Failed to load config from {config_path}: {e}. Using defaults.")

    # Override from environment variables if present (useful for Docker & CasaOS)
    if "SCAN_PATHS" in os.environ:
        paths = [p.strip() for p in os.environ["SCAN_PATHS"].split(",") if p.strip()]
        config["scan_paths"] = paths

    if "OUTPUT_DIR" in os.environ:
        config["output"]["report_directory"] = os.environ["OUTPUT_DIR"]

    if "DETECT_PARTIALS" in os.environ:
        config["detection"]["detect_fractional_chapters"] = os.environ["DETECT_PARTIALS"].lower() in ("true", "1", "yes")

    # Normalize scan paths
    normalized_paths: List[Path] = []
    for p in config.get("scan_paths", []):
        normalized_paths.append(normalize_path(p))
    config["normalized_scan_paths"] = normalized_paths

    return config
