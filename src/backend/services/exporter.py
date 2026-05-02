"""
슬라이드 PNG + 주석 래스터라이징 → PDF 내보내기

전략:
- Pillow로 PNG 이미지를 PDF 페이지로 합치기 (reportlab 필요 없이 Pillow JPEG2000 방식)
- 주석 JSON(Fabric.js)은 Phase 2에서 HTML canvas → PNG로 합성 예정
- Phase 1: 슬라이드 이미지만 PDF로 묶기
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image


def export_to_pdf(slides_dir: Path, out_path: Path) -> Path:
    """
    uploads/{file_id}/slides/page_01.png ~ page_NN.png → out_path (PDF)
    반환: out_path
    """
    png_files = sorted(slides_dir.glob("page_*.png"))
    if not png_files:
        raise FileNotFoundError(f"슬라이드 이미지 없음: {slides_dir}")

    images = [Image.open(p).convert("RGB") for p in png_files]
    first, rest = images[0], images[1:]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    first.save(
        str(out_path),
        "PDF",
        save_all=True,
        append_images=rest,
        resolution=150,
    )
    return out_path
