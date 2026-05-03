"""파일 업로드 / 슬라이드 메타 조회"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image

from services.converter import pdf_to_pngs, pptx_to_pngs

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOADS_DIR = Path("uploads")
ALLOWED_EXT = {".pdf", ".pptx"}
MAX_BYTES = 200 * 1024 * 1024  # 200MB

# 변환 진행 상태 저장소 (메모리, 단일 프로세스)
_conversion_progress: dict[str, dict] = {}


def _sse(data: dict) -> str:
    import json as _json
    return f"data: {_json.dumps(data, ensure_ascii=False)}\n\n"


def _safe_id(file_id: str) -> str:
    """경로 탐색 공격 방지: hex 32자만 허용"""
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    return file_id


@router.post("/upload")
async def upload_file(file: UploadFile):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"지원하지 않는 형식: {ext} (허용: {ALLOWED_EXT})")

    file_id = uuid.uuid4().hex
    file_dir = UPLOADS_DIR / file_id
    file_dir.mkdir(parents=True, exist_ok=True)
    original = file_dir / f"original{ext}"

    size = 0
    with original.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                shutil.rmtree(file_dir, ignore_errors=True)
                raise HTTPException(413, f"파일 크기 초과 (최대 {MAX_BYTES // 1024 // 1024}MB)")
            f.write(chunk)

    _conversion_progress[file_id] = {"status": "converting", "page": 0, "total": 0}

    slides_dir = file_dir / "slides"
    try:
        if ext == ".pdf":
            pages = pdf_to_pngs(original, slides_dir)
        else:
            pages = pptx_to_pngs(original, slides_dir)
    except Exception as e:
        _conversion_progress[file_id] = {"status": "error", "message": str(e)}
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
    _conversion_progress[file_id] = {"status": "done", "page": len(pages), "total": len(pages)}
    return metadata


@router.get("/upload/{file_id}/progress")
async def upload_progress(file_id: str):
    """SSE 스트림 — 변환 진행 상황 실시간 전송"""
    fid = _safe_id(file_id)

    async def event_stream():
        meta_path = UPLOADS_DIR / fid / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            yield _sse({"status": "done", "page": meta["pageCount"], "total": meta["pageCount"]})
            return

        for _ in range(120):
            state = _conversion_progress.get(fid, {"status": "waiting"})
            yield _sse(state)
            if state.get("status") in ("done", "error"):
                return
            slides_dir = UPLOADS_DIR / fid / "slides"
            if slides_dir.exists():
                done_pages = len(list(slides_dir.glob("page_*.png")))
                _conversion_progress[fid] = {**state, "page": done_pages}
            await asyncio.sleep(0.5)

        yield _sse({"status": "timeout"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("")
def list_files():
    if not UPLOADS_DIR.exists():
        return []
    result = []
    for meta_path in UPLOADS_DIR.glob("*/metadata.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            fid = meta.get("fileId", meta_path.parent.name)
            result.append({**meta, "thumbnail": f"/uploads/{fid}/slides/page_01.png"})
        except Exception:
            continue
    result.sort(key=lambda m: m.get("uploadedAt", ""), reverse=True)
    return result


@router.delete("/{file_id}")
def delete_file(file_id: str):
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


@router.post("/{file_id}/whiteboard")
def insert_whiteboard_page(file_id: str):
    fid = _safe_id(file_id)
    slides_dir = UPLOADS_DIR / fid / "slides"
    meta_path = UPLOADS_DIR / fid / "metadata.json"
    if not slides_dir.exists():
        raise HTTPException(404, "슬라이드를 찾을 수 없음")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    new_page = meta["pageCount"] + 1

    first_png = slides_dir / "page_01.png"
    if first_png.exists():
        ref = Image.open(first_png)
        width, height = ref.size
    else:
        width, height = 1920, 1080

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
