"""
슬라이드 PNG + 주석 래스터라이징 → PDF 내보내기

전략:
- Pillow로 PNG 이미지를 PDF 페이지로 합치기 (reportlab 필요 없이 Pillow JPEG2000 방식)
- 주석 JSON(Fabric.js)은 Phase 2에서 HTML canvas → PNG로 합성 예정
- Phase 1: 슬라이드 이미지만 PDF로 묶기
- Phase 2-3: 유인물 레이아웃 (1up/2up/4up) — A4 기준, 노트 텍스트 포함
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

# A4 @ 150 DPI
A4_W = 1240  # px (210mm)
A4_H = 1754  # px (297mm)
MARGIN = 60   # px
NOTE_LINE_H = 28  # px per line
NOTE_FONT_SIZE = 18
SLIDE_NOTE_GAP = 16


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """시스템 한글 폰트 시도, 없으면 기본 폰트."""
    candidates = [
        "malgun.ttf",           # Windows 맑은 고딕
        "NanumGothic.ttf",      # Linux NanumGothic
        "NotoSansCJK-Regular.ttc",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_note_lines(draw: ImageDraw.ImageDraw, x: int, y: int, w: int,
                     text: str, font, line_h: int, max_lines: int = 6):
    """노트 텍스트를 지정 영역에 줄 바꿈해 그리기. 빈 줄 구분선도 표시."""
    lines: list[str] = []
    if text:
        for raw in text.splitlines():
            wrapped = textwrap.wrap(raw or " ", width=max(1, w // (NOTE_FONT_SIZE // 2 + 2)))
            lines.extend(wrapped or [""])
    # 빈 줄 채우기 (노트 필기 공간)
    while len(lines) < max_lines:
        lines.append("")

    for i, line in enumerate(lines[:max_lines]):
        ty = y + i * line_h
        # 연한 줄 그리기
        draw.line([(x, ty + line_h - 4), (x + w, ty + line_h - 4)], fill="#cccccc", width=1)
        if line:
            draw.text((x, ty), line, fill="#222222", font=font)


def _resize_slide(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    return img


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


def export_handout(
    slides_dir: Path,
    notes_dir: Path,
    out_path: Path,
    layout: Literal["1up", "2up", "4up"] = "2up",
) -> Path:
    """
    유인물 레이아웃 PDF 내보내기.

    layout="1up": A4 1페이지에 슬라이드 1장 + 노트 영역 6줄
    layout="2up": A4 1페이지에 슬라이드 2장 + 각 노트 영역 4줄
    layout="4up": A4 1페이지에 슬라이드 4장 (2×2 그리드, 요약 인쇄용)
    """
    png_files = sorted(slides_dir.glob("page_*.png"))
    if not png_files:
        raise FileNotFoundError(f"슬라이드 이미지 없음: {slides_dir}")

    font = _load_font(NOTE_FONT_SIZE)
    pages_per_sheet = {"1up": 1, "2up": 2, "4up": 4}[layout]
    slide_count = len(png_files)

    # 페이지별 노트 텍스트 미리 로드
    note_texts: list[str] = []
    for idx in range(slide_count):
        page_num = idx + 1
        note_path = notes_dir / f"slide_{page_num:02d}.json"
        if note_path.exists():
            try:
                data = json.loads(note_path.read_text(encoding="utf-8"))
                note_texts.append(data.get("text", ""))
            except Exception:
                note_texts.append("")
        else:
            note_texts.append("")

    a4_pages: list[Image.Image] = []

    if layout == "1up":
        slide_w = A4_W - 2 * MARGIN
        slide_max_h = int(A4_H * 0.55)
        note_lines = 8
        for idx, png_path in enumerate(png_files):
            canvas = Image.new("RGB", (A4_W, A4_H), "white")
            draw = ImageDraw.Draw(canvas)
            slide_img = _resize_slide(Image.open(png_path), slide_w, slide_max_h)
            sx = MARGIN + (slide_w - slide_img.width) // 2
            canvas.paste(slide_img, (sx, MARGIN))
            note_y = MARGIN + slide_img.height + SLIDE_NOTE_GAP
            note_h = A4_H - note_y - MARGIN
            actual_lines = min(note_lines, note_h // NOTE_LINE_H)
            _draw_note_lines(draw, MARGIN, note_y, slide_w,
                             note_texts[idx], font, NOTE_LINE_H, actual_lines)
            a4_pages.append(canvas)

    elif layout == "2up":
        cell_w = A4_W - 2 * MARGIN
        cell_slide_h = int((A4_H - 2 * MARGIN - SLIDE_NOTE_GAP) * 0.40)
        note_lines = 4
        # 슬라이드 2장씩 한 페이지
        for sheet_i in range(0, slide_count, 2):
            canvas = Image.new("RGB", (A4_W, A4_H), "white")
            draw = ImageDraw.Draw(canvas)
            for slot, idx in enumerate([sheet_i, sheet_i + 1]):
                if idx >= slide_count:
                    break
                slot_top = MARGIN + slot * (A4_H - 2 * MARGIN) // 2
                slide_img = _resize_slide(Image.open(png_files[idx]), cell_w, cell_slide_h)
                sx = MARGIN + (cell_w - slide_img.width) // 2
                canvas.paste(slide_img, (sx, slot_top))
                note_y = slot_top + slide_img.height + SLIDE_NOTE_GAP // 2
                slot_bottom = MARGIN + (slot + 1) * (A4_H - 2 * MARGIN) // 2
                avail_h = slot_bottom - note_y - MARGIN // 2
                actual_lines = min(note_lines, max(1, avail_h // NOTE_LINE_H))
                _draw_note_lines(draw, MARGIN, note_y, cell_w,
                                 note_texts[idx], font, NOTE_LINE_H, actual_lines)
            # 슬롯 구분선
            mid_y = A4_H // 2
            draw.line([(MARGIN, mid_y), (A4_W - MARGIN, mid_y)], fill="#dddddd", width=2)
            a4_pages.append(canvas)

    else:  # 4up
        cols, rows = 2, 2
        cell_w = (A4_W - 2 * MARGIN - MARGIN) // cols
        cell_h = (A4_H - 2 * MARGIN - MARGIN) // rows
        for sheet_i in range(0, slide_count, 4):
            canvas = Image.new("RGB", (A4_W, A4_H), "white")
            draw = ImageDraw.Draw(canvas)
            for slot in range(4):
                idx = sheet_i + slot
                if idx >= slide_count:
                    break
                col = slot % cols
                row = slot // cols
                cx = MARGIN + col * (cell_w + MARGIN)
                cy = MARGIN + row * (cell_h + MARGIN)
                slide_img = _resize_slide(Image.open(png_files[idx]), cell_w, cell_h - 20)
                sx = cx + (cell_w - slide_img.width) // 2
                canvas.paste(slide_img, (sx, cy))
                # 슬라이드 번호
                draw.text((cx, cy + slide_img.height + 4),
                           f"슬라이드 {idx + 1}", fill="#888888", font=font)
            # 그리드 구분선
            mid_x = A4_W // 2
            mid_y = A4_H // 2
            draw.line([(mid_x, MARGIN), (mid_x, A4_H - MARGIN)], fill="#dddddd", width=1)
            draw.line([(MARGIN, mid_y), (A4_W - MARGIN, mid_y)], fill="#dddddd", width=1)
            a4_pages.append(canvas)

    if not a4_pages:
        raise RuntimeError("생성된 유인물 페이지 없음")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    first, rest = a4_pages[0], a4_pages[1:]
    first.save(str(out_path), "PDF", save_all=True, append_images=rest, resolution=150)
    return out_path

