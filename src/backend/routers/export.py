"""PDF 내보내기 엔드포인트"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.exporter import export_to_pdf

router = APIRouter()
UPLOADS_DIR = Path("uploads")


@router.get("/{file_id}")
def download_pdf(file_id: str):
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")

    slides_dir = UPLOADS_DIR / file_id / "slides"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    out_path = UPLOADS_DIR / file_id / "export.pdf"
    try:
        export_to_pdf(slides_dir, out_path)
    except Exception as e:
        raise HTTPException(500, f"PDF 생성 실패: {e}")

    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        filename=f"slidenote_{file_id[:8]}.pdf",
    )
