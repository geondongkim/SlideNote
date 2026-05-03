"""슬라이드별 노트 + 주석 저장/로드 (파일 기반, Phase 1)"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
UPLOADS_DIR = Path("uploads")


class Note(BaseModel):
    text: str = ""
    annotations: dict[str, Any] = Field(default_factory=dict)
    ai_summary: str = ""
    audio_url: str = ""
    audio_timestamps: dict[str, float] = Field(default_factory=dict)


def _note_path(file_id: str, page: int) -> Path:
    if len(file_id) != 32 or not all(c in "0123456789abcdef" for c in file_id):
        raise HTTPException(400, "잘못된 file_id")
    if page < 1:
        raise HTTPException(400, "page는 1 이상")
    notes_dir = UPLOADS_DIR / file_id / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir / f"slide_{page:02d}.json"


@router.get("/{file_id}/{page}")
def get_note(file_id: str, page: int) -> dict[str, Any]:
    path = _note_path(file_id, page)
    if not path.exists():
        return Note().model_dump() | {"updated_at": None}
    return json.loads(path.read_text(encoding="utf-8"))


@router.put("/{file_id}/{page}")
def save_note(file_id: str, page: int, note: Note) -> dict[str, Any]:
    path = _note_path(file_id, page)
    payload = note.model_dump() | {"updated_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
