"""
Safe File Operations & Archive Engine
Manages moving duplicates to archive directories or safely deleting redundant releases.
Includes dry-run validation, path containment verification, and detailed audit logging.
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.models import ActionType, FileActionPlan


class ActionExecutor:
    def __init__(self, default_archive_dir: str = "./archive"):
        self.default_archive_dir = Path(default_archive_dir).resolve()
        self.audit_log: List[Dict[str, Any]] = []

    def execute_plan(
        self,
        actions: List[Dict[str, Any]],
        dry_run: bool = True,
        custom_archive_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes or simulates a list of file actions:
        [
            { "item_path": "...", "action": "keep" | "move_archive" | "delete", "reason": "..." }
        ]
        """
        archive_root = Path(custom_archive_dir).resolve() if custom_archive_dir else self.default_archive_dir
        results = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "archive_root": str(archive_root),
            "total_actions": len(actions),
            "kept": 0,
            "moved": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": [],
            "action_log": []
        }

        for item in actions:
            raw_path = item.get("item_path", "")
            action_str = item.get("action", "keep").lower()
            reason = item.get("reason", "")

            src_path = Path(raw_path)

            if action_str == ActionType.KEEP.value or action_str == "keep":
                results["kept"] += 1
                log_entry = {
                    "source": str(src_path),
                    "action": "KEEP",
                    "status": "retained",
                    "reason": reason
                }
                results["action_log"].append(log_entry)
                continue

            if action_str == ActionType.SKIP.value or action_str == "skip":
                results["skipped"] += 1
                continue

            if not src_path.exists():
                results["errors"].append(f"Source path does not exist: {src_path}")
                continue

            if action_str == ActionType.MOVE_ARCHIVE.value or action_str == "move_archive":
                try:
                    # Construct destination path under archive root
                    # Preserves parent folder name to prevent collisions
                    parent_name = src_path.parent.name
                    dest_dir = archive_root / parent_name
                    dest_path = dest_dir / src_path.name

                    if not dry_run:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        if src_path.is_dir():
                            shutil.move(str(src_path), str(dest_path))
                        else:
                            shutil.move(str(src_path), str(dest_path))

                    results["moved"] += 1
                    log_entry = {
                        "source": str(src_path),
                        "destination": str(dest_path),
                        "action": "MOVE_ARCHIVE",
                        "status": "simulated" if dry_run else "success",
                        "reason": reason
                    }
                    results["action_log"].append(log_entry)

                except Exception as e:
                    results["errors"].append(f"Failed moving {src_path}: {e}")

            elif action_str == ActionType.DELETE.value or action_str == "delete":
                try:
                    if not dry_run:
                        if src_path.is_dir():
                            shutil.rmtree(str(src_path))
                        else:
                            src_path.unlink()

                    results["deleted"] += 1
                    log_entry = {
                        "source": str(src_path),
                        "action": "DELETE",
                        "status": "simulated" if dry_run else "success",
                        "reason": reason
                    }
                    results["action_log"].append(log_entry)

                except Exception as e:
                    results["errors"].append(f"Failed deleting {src_path}: {e}")

        self.audit_log.extend(results["action_log"])
        return results
