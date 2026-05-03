"""
Gemini Vision 슬라이드 요약 서비스

검증된 패턴 (gen_vision_improved.py 기반):
- PRIMARY: gemini-2.5-flash-image → inline_data 감지 시 FALLBACK: gemini-2.5-flash
- DELAY: 7.0초 (무료 티어 ~10 RPM 제한)
- 온도 0.1, max_tokens 8192
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

GEMINI_PRIMARY = "gemini-2.5-flash-image"
GEMINI_FALLBACK = "gemini-2.5-flash"
GEMINI_DELAY = 7.0

SLIDE_PROMPT = """다음 슬라이드 이미지를 보고 **발표자 노트 형식**으로 한국어 요약을 작성해 주세요.

## 작성 형식

### 핵심 요약 (3줄 이내)
슬라이드의 핵심 메시지 3줄

### 주요 내용
- 슬라이드에 담긴 주요 내용을 불릿으로 정리
- 다이어그램, 흐름도, 표가 있으면 설명 포함

### 발표 포인트
발표자가 강조해야 할 한 가지 포인트

---
Markdown 형식으로만 출력하세요. 마크다운 코드블록(```) 래퍼 없이 바로 내용만 출력하세요."""

# ── 슬라이드 → Markdown 변환용 프롬프트 (AI 요약과 별개) ──────────────────────
# 목적: Obsidian / Notion / NotebookLM 임포트에 최적화된 원문 충실 변환
# AI 요약(SLIDE_PROMPT)과의 차이:
#   SLIDE_PROMPT  → 3줄 핵심 요약 + 발표 포인트 (내용 압축)
#   SLIDE_TO_MARKDOWN_PROMPT → 슬라이드에 있는 모든 텍스트/표/다이어그램을 빠짐없이 구조화
SLIDE_TO_MARKDOWN_PROMPT = """이 슬라이드에 보이는 모든 내용을 **원문에 충실하게** Markdown으로 변환하세요.
요약하거나 내용을 줄이지 마세요. 슬라이드에 있는 텍스트는 모두 포함해야 합니다.

변환 규칙:
1. 슬라이드 제목/큰 헤딩 → `## 제목`
2. 소제목/섹션 → `### 소제목`
3. 본문 텍스트 계층 → 들여쓰기에 따라 `- ` / `  - ` 불릿
4. 표 → GFM 마크다운 표 형식 (`| 헤더 | 헤더 |\\n|---|---|\\n| 값 | 값 |`)
5. 흐름도/순서도/아키텍처 다이어그램 → Mermaid graph TD 코드블록
6. 시퀀스 다이어그램 → Mermaid sequenceDiagram 코드블록
7. 강조 박스/콜아웃 → `> 내용` (인용 형식)
8. 코드/명령어 → 인라인 `` `코드` `` 또는 코드블록
9. 이미지·차트만 있고 텍스트 없는 경우 → `[차트: 간단한 설명]`
10. 슬라이드 하단 출처/각주도 포함

출력: Markdown만. 코드블록(```) 래퍼 없이 바로 내용 출력. 한국어 그대로 유지."""


def _get_client():
    """google-genai 클라이언트 초기화. API 키는 환경변수 GOOGLE_API_KEY."""
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=api_key)


def _call_model(client, gtypes, model: str, img_path: Path) -> tuple[str, str | None]:
    """단일 모델 호출. 반환: (text, error_type|None)"""
    from PIL import Image

    try:
        img = Image.open(str(img_path))
        resp = client.models.generate_content(
            model=model,
            contents=[img, SLIDE_PROMPT],
            config=gtypes.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        text = resp.text or ""
        if not text.strip():
            return "", "inline_data"
        return text, None
    except Exception as e:
        err = str(e)
        if "inline_data" in err.lower() or "non-text" in err.lower():
            return "", "inline_data"
        return "", err


async def summarize_slide(img_path: Path) -> str:
    """
    슬라이드 PNG → 한국어 발표자 노트 요약 (Markdown).
    PRIMARY 실패 시 FALLBACK, GEMINI_DELAY 대기.
    """
    from google.genai import types as gtypes

    def _run() -> str:
        client = _get_client()
        text, err = _call_model(client, gtypes, GEMINI_PRIMARY, img_path)
        if err == "inline_data":
            logger.info("inline_data 감지 → %s 폴백", GEMINI_FALLBACK)
            import time
            time.sleep(GEMINI_DELAY)
            text, err = _call_model(client, gtypes, GEMINI_FALLBACK, img_path)
        if err:
            raise RuntimeError(f"Gemini 오류: {err}")
        return text

    # 동기 블로킹 함수를 이벤트 루프에서 실행
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def convert_slide_to_markdown(img_path: Path) -> str:
    """
    슬라이드 PNG → Obsidian/Notion/NotebookLM에 최적화된 구조화된 Markdown.

    AI 요약(summarize_slide)과 다름:
    - summarize_slide: 내용을 3줄로 압축하는 '발표자 노트 요약'
    - convert_slide_to_markdown: 슬라이드의 모든 내용을 빠짐없이 변환하는 '원문 충실 변환'
    """
    from google.genai import types as gtypes

    def _run() -> str:
        client = _get_client()

        # _call_model은 SLIDE_PROMPT를 하드코딩하므로 직접 호출
        img_bytes = img_path.read_bytes()
        suffix = img_path.suffix.lower().lstrip(".")
        mime = "image/png" if suffix == "png" else f"image/{suffix}"

        img_part = gtypes.Part.from_bytes(data=img_bytes, mime_type=mime)

        def _call(model: str) -> tuple[str, str | None]:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[img_part, SLIDE_TO_MARKDOWN_PROMPT],
                    config=gtypes.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=8192,
                    ),
                )
                text = resp.text or ""
                if not text.strip():
                    return "", "inline_data"
                return text, None
            except Exception as e:
                err = str(e)
                if "inline_data" in err.lower() or "non-text" in err.lower():
                    return "", "inline_data"
                return "", err

        text, err = _call(GEMINI_PRIMARY)
        if err == "inline_data":
            logger.info("inline_data 감지 → %s 폴백 (Markdown 변환)", GEMINI_FALLBACK)
            import time
            time.sleep(GEMINI_DELAY)
            text, err = _call(GEMINI_FALLBACK)
        if err:
            raise RuntimeError(f"Gemini Markdown 변환 오류: {err}")
        return text

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)
