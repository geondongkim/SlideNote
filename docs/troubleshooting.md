# 트러블슈팅 & 노하우

> PPTX/PDF 처리 파이프라인 개발 과정에서 축적된 실전 경험

---

## 1. PPTX → PNG 변환

### Windows: pywin32 (PowerPoint COM)

**권장 방식** — 가장 고품질 출력

```python
import win32com.client
import os

def _win32_pptx_to_pngs(pptx_path, out_dir, width=1920):
    pptx_abs = os.path.abspath(str(pptx_path))
    out_abs  = os.path.abspath(str(out_dir))
    os.makedirs(out_abs, exist_ok=True)

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = True  # ← 반드시 True (headless 시 일부 슬라이드 렌더링 실패)
    try:
        presentation = ppt.Presentations.Open(pptx_abs)
        for i, slide in enumerate(presentation.Slides):
            out_path = os.path.join(out_abs, f"page_{i+1:02d}.png")
            slide.Export(out_path, "PNG", width)  # width만 지정, 비율 자동
        presentation.Close()
    finally:
        ppt.Quit()
```

**주의사항:**
- `ppt.Visible = False` 또는 headless 시 일부 슬라이드 렌더링이 건너뛰어짐
- `presentation.Slides(p)` — COM은 **1-based 인덱스** 사용 (python-pptx의 0-based와 다름)
- `list(prs.slides)[:n]` — python-pptx의 `SlideMaster.slides`는 리스트로 변환 필요 (`[:n]` 슬라이싱 직접 불가)

### Linux/Mac: LibreOffice headless

```bash
# PPTX → PDF 변환 후 PyMuPDF로 PNG 추출
libreoffice --headless --convert-to pdf input.pptx --outdir /tmp/
python -c "import fitz; ..."
```

**주의사항:**
- LibreOffice 폰트 재현 불완전 (특히 한글 폰트)
- 복잡한 애니메이션/이펙트 무시됨

---

## 2. PDF → PNG 변환 (PyMuPDF)

### 최적 DPI 설정

| DPI | 용도 | 처리 속도 | 파일 크기 |
|-----|------|----------|---------|
| 72  | 썸네일 | 매우 빠름 | 작음 |
| **150** | **뷰어 + AI 분석** | **빠름** | **적당** |
| 300 | 인쇄용 | 2~3배 느림 | 큼 |

**권장: DPI=150** — 속도/품질/AI 인식률 최적 균형점

```python
matrix = fitz.Matrix(150/72, 150/72)  # DPI 150
pix = page.get_pixmap(matrix=matrix)
```

### 페이지 번호 (0-based vs 1-based)

```python
# PyMuPDF: 0-based
for i, page in enumerate(doc):  # i = 0, 1, 2, ...
    png_name = f"page_{i+1:02d}.png"  # 출력 파일명은 1-based

# 특정 페이지만 처리
pages = [1, 3, 5]  # 사용자 입력 (1-based)
for p in pages:
    page = doc[p - 1]  # 0-based로 변환
```

---

## 3. Gemini Vision API

### 모델 선택 전략

```
gemini-2.5-flash-image (primary)
    │
    ├─ 응답에 inline_data 포함? ──Yes──▶ gemini-2.5-flash (fallback)
    │                                          │
    └─ No ──▶ 마크다운 텍스트 반환          ──▶ 마크다운 텍스트 반환
```

**inline_data 감지 코드:**
```python
def has_inline_data(response) -> bool:
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'inline_data') and part.inline_data is not None:
            return True
    return False
```

### 슬라이드 유형별 모델 성능 (실측)

| 슬라이드 유형 | flash-image | flash | 추천 |
|-------------|------------|-------|------|
| 기술 다이어그램 (복잡) | 74.7 ⚠️ | **81.7** | flash |
| 비즈니스 리포트 디자인 | 폴백⚠️ | **~20** | flash |
| 데이터 차트/그래프 | **100.6** | 35.8 | flash-image |
| 텍스트 위주 | **17.4** | 14.8 | flash-image |

**결론:** 콘텐츠 유형을 알 수 없으면 `flash-image` 우선 + 폴백 전략이 최선

### Rate Limit 대응

```python
GEMINI_DELAY = 7.0  # 무료 티어 ~10 RPM → 6초 이상 간격 필요 (여유 1초)

# 배치 처리 시
import time
for i, slide in enumerate(slides):
    result = call_gemini(slide)
    if i < len(slides) - 1:
        time.sleep(GEMINI_DELAY)
```

**유료 티어 전환 시**: `GEMINI_DELAY = 1.0`으로 줄여도 됨

### 효과적인 슬라이드 프롬프트

```python
SLIDE_PROMPT = """
당신은 슬라이드 분석 전문가입니다. 이 슬라이드를 구조화된 Markdown으로 변환하세요.

규칙:
1. 계층 구조는 ## / ### / #### 헤더로 표현
2. 테이블 → HTML <table> (colspan/rowspan 포함)
3. 흐름도/순서도 → Mermaid ```graph TD```
4. 시퀀스 다이어그램 → Mermaid ```sequenceDiagram```
5. 일정/간트 → Mermaid ```gantt```
6. 강조 박스 → > blockquote
7. 코드/명령어 → ```언어 코드블록```
8. **절대로 이미지를 생성하지 마세요** — 텍스트 Markdown만 출력

{extra_context}
"""
```

`{extra_context}`에 python-pptx로 추출한 텍스트를 추가하면 인식률 향상 (특히 작은 폰트 텍스트)

---

## 4. python-pptx 주의사항

### 슬라이드 인덱싱

```python
from pptx import Presentation

prs = Presentation("file.pptx")

# ✅ 올바른 방법
slides_list = list(prs.slides)  # list로 변환 필수
for i, slide in enumerate(slides_list):
    ...  # i: 0-based

# ❌ 직접 슬라이싱 불가
# prs.slides[:5]  → AttributeError
```

### 메타데이터 추출

```python
def extract_slide_metadata(slide) -> str:
    """AI 프롬프트 보강용 구조 텍스트"""
    lines = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if text:
                    lines.append(text)
        if shape.has_table:
            table = shape.table
            lines.append(f"[테이블 {table.rows.__len__()}행 x {table.columns.__len__()}열]")
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                lines.append(row_text)
    return "\n".join(lines)
```

---

## 5. 주석 레이어 (Fabric.js)

### Canvas 크기 맞춤

```js
// 슬라이드 이미지 로드 후 Canvas 크기 동기화
const img = new Image();
img.onload = () => {
  canvas.setWidth(img.naturalWidth);
  canvas.setHeight(img.naturalHeight);
  canvas.setBackgroundImage(
    new fabric.Image(img),
    canvas.renderAll.bind(canvas)
  );
};
```

### 주석 JSON 저장 형식

```json
{
  "version": "6.0.0",
  "objects": [
    {
      "type": "path",
      "path": "M 100 200 L 150 180...",
      "stroke": "#e74c3c",
      "strokeWidth": 2,
      "fill": "transparent",
      "_timestamp": 32.5
    }
  ]
}
```

`_timestamp` 커스텀 필드로 오디오 연동 구현

---

## 6. PDF 내보내기 (주석 병합)

### 전략: Canvas PNG + PyMuPDF 합성

```python
import fitz

def export_annotated_pdf(file_id: str) -> Path:
    output = fitz.open()
    slides = get_slides(file_id)
    
    for slide_num, slide_png in enumerate(slides, 1):
        # 슬라이드 PNG를 PDF 페이지로
        img_doc = fitz.open(str(slide_png))
        page = output.new_page(width=img_doc[0].rect.width,
                               height=img_doc[0].rect.height)
        page.show_pdf_page(page.rect, img_doc, 0)
        
        # 주석 레이어 PNG 합성
        annotation_png = get_annotation_png(file_id, slide_num)
        if annotation_png:
            page.insert_image(page.rect, filename=str(annotation_png))
        
        # 노트 텍스트를 PDF 하단에 추가
        note = get_note_text(file_id, slide_num)
        if note:
            page.insert_textbox(
                fitz.Rect(20, page.rect.height - 100, page.rect.width - 20, page.rect.height - 10),
                note, fontsize=9, color=(0.2, 0.2, 0.2)
            )
    
    out_path = Path(f"uploads/{file_id}/export.pdf")
    output.save(str(out_path))
    return out_path
```

---

## 7. SyntaxWarning 방지 (Python)

프롬프트 문자열에 백틱(`) 포함 시 escape 문자 사용 금지:

```python
# ❌ SyntaxWarning 발생
PROMPT = "코드는 \`코드블록\`으로"

# ✅ 올바른 방법 (삼중 따옴표 내 직접 사용)
PROMPT = """코드는 ```언어
코드블록
```으로"""
```

---

## 8. 환경 변수 & 보안

```python
# .env (절대 git에 커밋 금지)
GOOGLE_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj-...
FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}

# .gitignore에 반드시 포함
# .env
# uploads/          ← 사용자 업로드 파일
# __pycache__/
# *.pyc
```

---

## 9. PowerShell 2>&1 리다이렉션 주의

PowerShell에서 Python 스크립트 실행 시 stderr 경고가 exit code 1로 처리될 수 있음:

```powershell
# urllib3 버전 불일치 경고 → PowerShell이 오류로 처리 → exit code 1
python script.py 2>&1

# 해결: Python 내부에서 경고 억제
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

실제 스크립트 성공 여부는 마지막 출력 메시지(`완료!`)로 확인.
