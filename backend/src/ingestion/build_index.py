"""
build_index.py — Lệnh cũ dựng vector store bằng embedding LOCAL.

ĐÃ ĐƯỢC THAY THẾ: pipeline chuyển sang Voyage AI embedding API (không tải
model local — chạy được trên Render free tier 512MB). Lệnh mới:

    python scripts/rebuild_vector_store.py

File này chỉ còn là shim giữ tương thích lệnh cũ + hàm collect_source_files
cho các script khác import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def collect_source_files(raw_dir: Path) -> list[Path]:
    """Quét file quy chế trong data/raw (bỏ file tạm ~$ của Word)."""
    files = sorted(raw_dir.glob("*.docx")) + sorted(raw_dir.glob("*.pdf"))
    files = [f for f in files if not f.name.startswith("~$")]
    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file PDF/DOCX nào trong {raw_dir}/ — "
            "hãy copy file quy chế vào thư mục này trước.")
    return files


def main() -> None:
    print("build_index (embedding local) đã được thay bằng "
          "scripts/rebuild_vector_store.py (Voyage embedding API).")
    print("Chuyển sang chạy: python scripts/rebuild_vector_store.py")
    # Chạy thẳng script mới — cùng cwd backend/, cùng đọc .env
    script = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_vector_store.py"
    sys.argv = [str(script)] + sys.argv[1:]
    code = compile(script.read_text(encoding="utf-8"), str(script), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(script)})


if __name__ == "__main__":
    main()
