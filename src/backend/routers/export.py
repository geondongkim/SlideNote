"""PDF 내보내기 엔드포인트"""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from services.exporter import export_to_pdf, export_handout

router = APIRouter()
UPLOADS_DIR = Path("uploads")


def _validate_id(file_id: str) -> str:
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    return file_id


@router.get("/{file_id}")
def download_pdf(file_id: str):
    fid = _validate_id(file_id)
    slides_dir = UPLOADS_DIR / fid / "slides"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    out_path = UPLOADS_DIR / fid / "export.pdf"
    try:
        export_to_pdf(slides_dir, out_path)
    except Exception as e:
        raise HTTPException(500, f"PDF 생성 실패: {e}")

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=f"slidenote_{fid[:8]}.pdf",
    )


@router.get("/{file_id}/handout")
def download_handout(
    file_id: str,
    layout: Literal["1up", "2up", "4up"] = Query(default="2up"),
):
    """유인물 레이아웃 PDF 다운로드. layout=1up|2up|4up"""
    fid = _validate_id(file_id)
    slides_dir = UPLOADS_DIR / fid / "slides"
    notes_dir = UPLOADS_DIR / fid / "notes"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    out_path = UPLOADS_DIR / fid / f"handout_{layout}.pdf"
    try:
        export_handout(slides_dir, notes_dir, out_path, layout=layout)
    except Exception as e:
        raise HTTPException(500, f"유인물 PDF 생성 실패: {e}")

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=f"slidenote_{fid[:8]}_handout_{layout}.pdf",
    )

