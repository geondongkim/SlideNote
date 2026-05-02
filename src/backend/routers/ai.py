"""AI 요약 엔드포인트"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.gemini import summarize_slide

logger = logging.getLogger(__name__)
router = APIRouter()
UPLOADS_DIR = Path("uploads")


class SummarizeRequest(BaseModel):
    page: int


@router.post("/{file_id}/summarize")
async def summarize(file_id: str, req: SummarizeRequest):
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    if req.page < 1:
        raise HTTPException(400, "page는 1 이상")

    img_path = UPLOADS_DIR / file_id / "slides" / f"page_{req.page:02d}.png"
    if not img_path.exists():
        raise HTTPException(404, f"슬라이드 {req.page}를 찾을 수 없음")

    try:
        summary = await summarize_slide(img_path)
    except ValueError as e:
        raise HTTPException(503, str(e))
    except RuntimeError as e:
        logger.exception("Gemini 요약 실패")
        raise HTTPException(502, str(e))

    # 노트 파일에 ai_summary 업데이트
    note_path = UPLOADS_DIR / file_id / "notes" / f"slide_{req.page:02d}.json"
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
    else:
        note = {"text": "", "annotations": {}, "ai_summary": "", "updated_at": None}
    note["ai_summary"] = summary
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"fileId": file_id, "page": req.page, "summary": summary}
