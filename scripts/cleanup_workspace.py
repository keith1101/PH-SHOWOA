"""
CLEANUP WORKSPACE SCRIPT (WINDOWS READ-ONLY HANDLER INCLUDED)
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Protected directories that must NEVER be deleted
PROTECTED = {
    ".git", ".agents", ".vscode", "data", "outputs",
    "scripts", "src_canonical", "src_paper_literal", "src",
    "tests", "docs", "reports", "utils", "node_modules"
}


def remove_readonly(func, path, exc_info):
    """Clear the read-only bit and retry removal."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"Failed to force-delete {path}: {e}")


def get_dir_size(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def main():
    tmp_path = ROOT / "tmp"
    if tmp_path.is_dir() and tmp_path.name not in PROTECTED:
        sz = get_dir_size(tmp_path)
        print(f"Removing remaining tmp/ folder ({sz / (1024*1024):.2f} MB)...")
        shutil.rmtree(tmp_path, onerror=remove_readonly)
        print(f"[REMOVED DIR] tmp ({sz / (1024*1024):.2f} MB)")
    else:
        print("tmp directory already clean or not found.")


if __name__ == "__main__":
    main()
