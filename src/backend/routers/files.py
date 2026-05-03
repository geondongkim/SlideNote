"""파일 업로드 / 슬라이드 메타 조회"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image

from services.converter import pdf_to_pngs, pptx_to_pngs

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOADS_DIR = Path("uploads")
ALLOWED_EXT = {".pdf", ".pptx"}
MAX_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/upload")
async def upload_file(file: UploadFile):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"지원하지 않는 형식: {ext} (허용: {ALLOWED_EXT})")

    file_id = uuid.uuid4().hex
    file_dir = UPLOADS_DIR / file_id
    file_dir.mkdir(parents=True, exist_ok=True)
    original = file_dir / f"original{ext}"

    # 50MB 제한 검사 + 저장
    size = 0
    with original.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                shutil.rmtree(file_dir, ignore_errors=True)
                raise HTTPException(413, f"파일 크기 초과 (최대 {MAX_BYTES // 1024 // 1024}MB)")
            f.write(chunk)

    slides_dir = file_dir / "slides"
    try:
        if ext == ".pdf":
            pages = pdf_to_pngs(original, slides_dir)
        else:
            pages = pptx_to_pngs(original, slides_dir)
    except Exception as e:
        logger.exception("변환 실패")
        shutil.rmtree(file_dir, ignore_errors=True)
        raise HTTPException(500, f"변환 실패: {e}")

    metadata = {
        "fileId": file_id,
        "filename": file.filename,
        "ext": ext,
        "pageCount": len(pages),
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
    }
    (file_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


@router.get("")
def list_files():
    """uploads/ 아래 모든 파일의 메타데이터 목록 반환 (최신순)"""
    if not UPLOADS_DIR.exists():
        return []
    result = []
    for meta_path in UPLOADS_DIR.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            # 첫 슬라이드 썸네일 URL
            fid = meta.get("fileId", meta_path.parent.name)
            thumb = f"/uploads/{fid}/slides/page_01.png"
            result.append({**meta, "thumbnail": thumb})
        except Exception:
            continue
    result.sort(key=lambda m: m.get("uploadedAt", ""), reverse=True)
    return result


@router.delete("/{file_id}")
def delete_file(file_id: str):
    """파일 및 관련 데이터 삭제"""
    fid = _safe_id(file_id)
    file_dir = UPLOADS_DIR / fid
    if not file_dir.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")
    shutil.rmtree(file_dir)
    return {"deleted": file_id}


@router.get("/{file_id}")
def get_file_meta(file_id: str):
    meta = UPLOADS_DIR / _safe_id(file_id) / "metadata.json"
    if not meta.exists():
        raise HTTPException(404, "파일을 찾을 수 없음")
    return json.loads(meta.read_text(encoding="utf-8"))


@router.get("/{file_id}/slides")
def list_slides(file_id: str):
    meta = get_file_meta(file_id)
    return {
        "fileId": file_id,
        "pageCount": meta["pageCount"],
        "slides": [
            {"page": i, "url": f"/uploads/{file_id}/slides/page_{i:02d}.png"}
            for i in range(1, meta["pageCount"] + 1)
        ],
    }


def _safe_id(file_id: str) -> str:
    """경로 탐색 공격 방지: hex 32자만 허용"""
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    return file_id


@router.post("/{file_id}/whiteboard")
def insert_whiteboard_page(file_id: str):
    """
    슬라이드 목록 마지막에 빈 흰 페이지(화이트보드)를 삽입한다.
    - 기존 슬라이드들의 크기를 참조해 동일 해상도 흰 PNG 생성
    - metadata.json pageCount 증가
    - 반환: { page, url }
    """
    fid = _safe_id(file_id)
    slides_dir = UPLOADS_DIR / fid / "slides"
    meta_path = UPLOADS_DIR / fid / "metadata.json"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    new_page = meta["pageCount"] + 1

    # 첫 슬라이드 크기 참조; 없으면 16:9 기본값
    first_png = slides_dir / "page_01.png"
    if first_png.exists():
        ref = Image.open(first_png)
        width, height = ref.size
    else:
        width, height = 1920, 1080

    # 빈 흰 PNG 생성
    blank = Image.new("RGB", (width, height), "white")
    out_path = slides_dir / f"page_{new_page:02d}.png"
    blank.save(str(out_path), "PNG")

    meta["pageCount"] = new_page
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "page": new_page,
        "url": f"/uploads/{fid}/slides/page_{new_page:02d}.png",
        "pageCount": new_page,
    }
