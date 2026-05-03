# 트러블슈팅 & 노하우

> PPTX/PDF 처리 파이프라인 개발 과정에서 축적된 실전 경험

---

## 1. PPTX → PNG 변환

### Windows: pywin32 (PowerPoint COM) — subprocess 패턴 필수

**⚠️ 중요**: uvicorn 이벤트루프 스레드에서 `win32com.client.Dispatch()` 직접 호출 시 COM STA 충돌 오류(`0x80048240`) 발생.  
**해결책**: 별도 Python subprocess + 임시 .py 파일 패턴을 사용.

```python
import sys, subprocess, tempfile
from pathlib import Path

def _win32_pptx_to_pngs(pptx_path: Path, out_dir: Path) -> list[Path]:
    abs_pptx = str(pptx_path.resolve())
    abs_out  = str(out_dir.resolve())

    # COM 코드를 별도 프로세스로 격리 (STA 스레드 보장)
    py_script = f"""\
import pythoncom, win32com.client
from pathlib import Path
pythoncom.CoInitialize()
app = win32com.client.DispatchEx('PowerPoint.Application')
app.Visible = True  # 반드시 True (headless 시 렌더링 실패)
try:
    prs = app.Presentations.Open({abs_pptx!r}, False, False, True)
    try:
        for i in range(1, prs.Slides.Count + 1):
            png = str(Path({abs_out!r}) / f'page_{{i:02d}}.png')
            prs.Slides(i).Export(png, 'PNG', 1920)  # PNG_WIDTH=1920
        print(prs.Slides.Count)
    finally:
        prs.Close()
finally:
    try: app.Quit()
    except: pass
    pythoncom.CoUninitialize()
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(py_script)
        tmp = f.name
    try:
        result = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=300)
    finally:
        Path(tmp).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"PPTX COM 변환 실패:\n{result.stderr.strip()}")
    return sorted(out_dir.glob('page_*.png'))
```

**핵심 포인트:**
- `DispatchEx` 사용 (`Dispatch` 대신) — 새 인스턴스 강제 생성으로 기존 프로세스 간섭 방지
- `Open(path, ReadOnly, Untitled, WithWindow)` — `WithWindow=True` (=`Visible=True` 동치)
- COM 1-based 인덱스: `prs.Slides(i)` (1부터 시작), python-pptx의 0-based와 다름
- `pythoncom.CoInitialize()` / `CoUninitialize()` — subprocess 내에서도 명시적 초기화 필요

### Linux/Mac: LibreOffice headless

```bash
# PPTX → PDF 변환 후 PyMuPDF로 PNG 추출
libreoffice --headless --convert-to pdf input.pptx --outdir /tmp/
python -c "import fitz; ..."
```

**주의사항:**
- LibreOffice 폰트 재현 불완전 (특히 한글 폰트)
- 복잡한 애니메이션/이펙트 무시됨

### Docker 환경: Gotenberg

Linux/Docker 환경에서 `GOTENBERG_URL` 환경변수를 설정하면 LibreOffice 대신 Gotenberg 사용:

```python
# _gotenberg_pptx_to_pngs() 흐름
import httpx
resp = httpx.Client(timeout=300).post(
    f"{gotenberg_url}/forms/libreoffice/convert",
    files={"files": (pptx_path.name, open(pptx_path, 'rb'), 'application/vnd.openxmlformats...')},
)
# PDF bytes → 임시 파일 → pdf_to_pngs()
```

```bash
# docker-compose.yml
services:
  gotenberg:
    image: gotenberg/gotenberg:8
    ports: ["3000:3000"]

# 백엔드 서비스 환경변수
GOTENBERG_URL=http://gotenberg:3000
```

---

## 1-B. PPTX → 고품질 PDF 변환 (벡터 보존)

래스터 PNG와 달리 벡터·폰트·하이퍼링크를 완전 보존하는 PDF 직접 변환:

### Windows: PowerPoint COM SaveAs

```python
# ppSaveAsPDF = 32 상수 (PowerPoint 2007+)
py_script = f"""\
import pythoncom, win32com.client
pythoncom.CoInitialize()
app = win32com.client.DispatchEx('PowerPoint.Application')
app.Visible = True
prs = app.Presentations.Open({abs_pptx!r}, False, False, True)
prs.SaveAs({abs_pdf!r}, 32)  # ppSaveAsPDF = 32
prs.Close()
app.Quit()
pythoncom.CoUninitialize()
"""
```

- `SaveAs(path, 32)` — 두 번째 인자가 저장 형식 (32 = PDF)
- 하이퍼링크, 폰트 임베딩, 투명도 레이어 모두 보존

### Linux: Gotenberg PDF bytes 직접 저장

```python
# PNG 변환과 달리 PDF bytes를 그대로 파일로 저장
resp = httpx.Client(timeout=300).post(endpoint, files={...})
resp.raise_for_status()
out_path.write_bytes(resp.content)  # 재변환 없음 → 원본 품질 유지
```

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

### 주석 JSON 저장 형식 (실제 스키마)

```json
{
  "fabricVersion": "6.6.1",
  "objects": [
    {
      "id": "<uuid>",
      "type": "path",
      "_pageRatio": [1920, 1080],
      "_timestamp": 32.5,
      "path": "M 100 200 L 150 180...",
      "stroke": "#e74c3c",
      "strokeWidth": 2,
      "fill": "transparent"
    }
  ]
}
```

- `id`, `_pageRatio` 필드는 모든 주석 객체에 필수
- `Fabric.toJSON(['id', '_pageRatio', '_timestamp'])` 로 직렬화
- `_pageRatio`: 저장 당시 뷰포트 크기 → 해상도 무관 위치 복원에 사용

### Eraser 도구 — useEffect cleanup 패턴

Fabric.js 이벤트를 `canvas.on()`으로 등록할 때 **cleanup 반환 필수**:

```js
useEffect(() => {
  if (!canvas || tool !== 'eraser') return

  canvas.isDrawingMode = false
  canvas.selection = false
  let erasing = false

  const onDown = () => { erasing = true }
  const onUp   = () => { erasing = false }
  const onMove = (opt) => {
    if (!erasing) return
    const ptr = canvas.getPointer(opt.e)
    const targets = canvas.getObjects().filter(obj => obj.containsPoint(ptr))
    if (targets.length) {
      targets.forEach(obj => canvas.remove(obj))
      canvas.renderAll()
    }
  }

  canvas.on('mouse:down', onDown)
  canvas.on('mouse:up', onUp)
  canvas.on('mouse:move', onMove)

  // ⚠️ cleanup 없으면 도구 전환 시 이전 핸들러가 남아 이벤트 중복 발생
  return () => {
    canvas.off('mouse:down', onDown)
    canvas.off('mouse:up', onUp)
    canvas.off('mouse:move', onMove)
  }
}, [canvas, tool])

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

---

## 10. Docker / nginx SSE 지원

### nginx에서 SSE 비활성화 문제

nginx 기본 설정은 응답을 버퍼링하여 SSE 이벤트가 즉시 전달되지 않음:

```nginx
# nginx.conf — /api/ 프록시 블록에 아래 설정 필수
location /api/ {
    proxy_pass http://backend:8000/;
    proxy_buffering     off;           # ← 버퍼링 비활성화 (SSE 필수)
    proxy_cache         off;
    proxy_read_timeout  3600;          # 장시간 변환 (PPTX→PDF 등) 대응
    proxy_set_header Connection '';
    chunked_transfer_encoding on;
}
```

FastAPI `StreamingResponse` 헤더에도 추가 설정:

```python
return StreamingResponse(
    stream(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # ← nginx upstream에 버퍼링 비활성화 지시
    },
)
```

### Docker compose 포트 충돌

```bash
# 포트 사용 중 확인 (Windows PowerShell)
netstat -ano | Select-String ":80 "

# docker-compose.yml 포트 변경 예시
ports:
  - "8080:80"   # 충돌 시 호스트 포트만 변경
```

### Windows 로컬 vs Docker 환경 분기

```
Windows 로컬 개발:
  win32com (PowerPoint 설치 필요) → PPTX→PNG/PDF 최고 품질
  GOTENBERG_URL 미설정 → Gotenberg 비활성

Linux/Docker:
  GOTENBERG_URL=http://gotenberg:3000 → LibreOffice API 사용
  win32com 없음 → Gotenberg 또는 LibreOffice headless 폴백
```

