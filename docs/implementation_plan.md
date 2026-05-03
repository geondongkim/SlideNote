# SlideNote 구현 계획

> PPTX / PDF 혼용 슬라이드 노트 앱 — 단계별 개발 로드맵

---

## 목표 & 범위

### 해결하는 문제
- 발표자: 슬라이드와 발표 대본을 한 화면에서 관리
- 학생: PDF 강의자료 위에 직접 필기·주석 추가
- 청중: 슬라이드 캡처 + 즉시 메모 작성

### 핵심 가치
1. **포맷 무관**: PPTX든 PDF든 동일한 UX 제공
2. **주석 비파괴**: 원본 파일을 수정하지 않고 레이어로 관리
3. **AI 보조**: Gemini Vision으로 슬라이드 내용 자동 요약

---

## 아키텍처 결정

### 왜 Python 백엔드인가?

기존 PPTX/PDF → Markdown 변환 파이프라인 개발에서 검증된 라이브러리를 그대로 활용합니다:

| 검증된 라이브러리 | 역할 | 검증 근거 |
|----------------|------|----------|
| `PyMuPDF` | PDF → PNG | 44페이지 변환 완료, DPI 150 최적 |
| `python-pptx` | PPTX 메타 추출 | 22슬라이드 구조 분석 완료 |
| `pywin32` | PPTX → PNG (Windows) | 1920px 고품질 출력 검증 |
| `google-genai` | Gemini Vision AI | 3종 모델 비교 완료 |

### 렌더링 전략

```
[업로드]
  PPTX ──▶ pywin32/LibreOffice ──▶ PNG (서버)
  PDF  ──▶ PyMuPDF              ──▶ PNG (서버)
                                      │
                              [FastAPI 정적 제공]
                                      │
[브라우저]                            ▼
  <img src="/slides/page_01.png"> + Fabric.js Canvas (주석 오버레이)
```

**PDF.js를 쓰지 않는 이유**: 브라우저 내 PDF 렌더링은 폰트/레이아웃 재현 불안정. 서버에서 PNG로 변환 후 제공하는 방식이 더 일관성 있음 (파이프라인 경험에서 검증).

---

## Phase 1: MVP (2~3주)

> **진행 상태 (2026-05-03)**: 1주차 백엔드/프론트 골격 구현 완료
> - ✅ `services/converter.py` (pdf_to_pngs / pptx_to_pngs Windows·LibreOffice 분기)
> - ✅ `routers/files.py` (`POST /api/files/upload`, `GET /{id}/slides`, 50MB 제한, file_id sanitize)
> - ✅ `routers/notes.py` (`GET/PUT /api/notes/{file_id}/{page}` 파일 기반 JSON)
> - ✅ 프론트 `lib/api.js`, `store/useAppStore.js`, `components/UploadButton.jsx`, `SlideList.jsx`
> - ✅ App.jsx 통합 + 노트 자동 저장 (500ms 디바운스)
> - ⏭️ 다음: Fabric.js Canvas 주석, PDF 내보내기, 단위 테스트

### 1-1. 백엔드 기반 (`src/backend/`)

#### `services/converter.py`

```python
# PPTX → PNG (Windows: win32com, 그 외: LibreOffice)
def pptx_to_pngs(pptx_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """
    검증된 전략 (gen_vision_improved.py 참조):
    - Windows: PowerPoint COM automation (PNG_WIDTH=1920)
    - Linux/Mac: LibreOffice --headless --convert-to pdf, 이후 PyMuPDF
    - 반환: [page_01.png, page_02.png, ...]
    """
    import platform
    if platform.system() == "Windows":
        return _win32_pptx_to_pngs(pptx_path, out_dir)
    else:
        return _libreoffice_pptx_to_pngs(pptx_path, out_dir, dpi)

def pdf_to_pngs(pdf_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """
    PyMuPDF 기반 (검증됨):
    - DPI 150: 속도/품질 최적 균형 (300은 2~3배 느림)
    - 출력: page_01.png ~ page_NN.png
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(dpi/72, dpi/72)
    results = []
    for i, page in enumerate(doc):
        png_path = out_dir / f"page_{i+1:02d}.png"
        pix = page.get_pixmap(matrix=matrix)
        pix.save(str(png_path))
        results.append(png_path)
    return results
```

#### `services/gemini.py`

```python
# 검증된 Gemini Vision 호출 패턴 (gen_vision_improved.py 참조)
GEMINI_PRIMARY   = "gemini-2.5-flash-image"
GEMINI_FALLBACK  = "gemini-2.5-flash"
GEMINI_DELAY_SEC = 7.0  # 무료 티어 rate limit (~10 RPM)

def call_gemini_smart(client, img_path: Path, context: str = "") -> tuple[str, str]:
    """
    inline_data 자동 감지 → 폴백 전략 (검증됨):
    - flash-image 응답에 inline_data 포함 시 → flash로 재시도
    - 이유: flash-image는 디자인 요소 많은 슬라이드에서 이미지 재생성 시도
    반환: (markdown_text, model_used)
    """
    ...
```

#### `routers/files.py`

```python
@router.post("/upload")
async def upload_file(file: UploadFile):
    """
    1. 파일 저장 (uploads/{file_id}/)
    2. 확장자 감지: .pptx → pptx_to_pngs(), .pdf → pdf_to_pngs()
    3. 슬라이드 수, 썸네일 URL 목록 반환
    4. PPTX의 경우 python-pptx로 메타데이터도 추출하여 저장
    """
```

#### `routers/notes.py`

```python
# 노트 저장 형식 (파일 기반, Phase 1)
# uploads/{file_id}/notes/slide_{n:02d}.json
#
# pdfanno(paperai/pdfanno)의 스키마를 참고하여 정규화된 좌표 방식 채택
# - id: UUID (pdfanno 방식)
# - page: 1-based 페이지 번호 (pdfanno 방식과 동일)
# - type: 'rect' | 'span' | 'path' | 'text' (pdfanno 타입 체계 확장)
# - position: [x, y, width, height]  — 뷰포트 상대 비율(0~1)로 정규화
#   → 해상도 변경에도 주석 위치 유지 (pdfanno의 convertFromExportY 아이디어)
#
# {
#   "version": "1.0",
#   "fileId": "...",
#   "page": 1,
#   "text": "발표 대본...",
#   "annotations": {
#     "fabricVersion": "6.6.1",
#     "objects": [                    # Fabric.js toJSON() 결과
#       {
#         "id": "<uuid>",            # 추가 필드
#         "type": "path",
#         "_pageRatio": [1.0, 0.75], # 저장 당시 이미지 비율 (리사이즈 복원용)
#         "_timestamp": 32.5,        # 오디오 타임스탬프 (Phase 2)
#         ...                        # Fabric.js 표준 필드
#       }
#     ]
#   },
#   "ai_summary": "...",
#   "updated_at": "2026-05-03T..."
# }
```

### 1-2. 프론트엔드 기반 (`src/frontend/`)

#### 3단 레이아웃 구조

```jsx
// App.jsx
<div className="flex h-screen">
  {/* 좌측: 슬라이드 목록 (200px) */}
  <SlideList slides={slides} current={current} onSelect={setCurrent} />
  
  {/* 중앙: 뷰어 + 주석 Canvas (flex-1) */}
  <SlideViewer slideUrl={slideUrl} annotations={annotations} />
  
  {/* 우측: 노트 에디터 (320px) */}
  <NoteEditor note={note} onSave={saveNote} onAI={requestAI} />
</div>
```

#### `usePdfRenderer.js` (서버 PNG 방식)

```js
// PDF.js 대신 서버 변환 PNG 사용 → 더 일관된 렌더링
export function useSlideImage(fileId, slideNum) {
  return `/api/files/${fileId}/slide/${slideNum}`;
}
```

#### `useAnnotation.js` (Fabric.js + drauu 패턴 참고)

```js
// Slidev(slidevjs/slidev)의 useDrawings.ts + pympress scribble.py 패턴 적용
export function useAnnotation(canvasRef) {
  // ── 도구 상태 (Slidev brushColors 팔레트 참고) ──
  const BRUSH_COLORS = ['#ff595e','#ffca3a','#8ac926','#1982c4','#6a4c93','#ffffff','#000000'];
  const [tool, setTool]   = useState('select'); // pen | highlight | rect | text | arrow
  const [color, setColor] = useState(BRUSH_COLORS[0]);
  const [width, setWidth] = useState(2);

  // ── Undo/Redo 스택 (pympress scribble_list / scribble_redo_list 패턴) ──
  // Fabric.js는 내장 history 없음 → 스냅샷 스택으로 직접 구현
  const historyRef   = useRef([]);  // [{objects: [...], timestamp}]
  const redoStackRef = useRef([]);

  const saveSnapshot = () => {
    historyRef.current.push(canvas.toJSON(['id','_timestamp','_pageRatio']));
    redoStackRef.current = [];      // redo 스택 클리어 (pympress scribble_drawing 패턴)
    if (historyRef.current.length > 50) historyRef.current.shift(); // max 50
  };

  const undo = () => {
    if (historyRef.current.length < 2) return;
    redoStackRef.current.push(historyRef.current.pop());
    canvas.loadFromJSON(historyRef.current.at(-1), () => canvas.renderAll());
  };

  const redo = () => {
    if (!redoStackRef.current.length) return;
    const next = redoStackRef.current.pop();
    historyRef.current.push(next);
    canvas.loadFromJSON(next, () => canvas.renderAll());
  };

  const enablePen = () => {
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.color = color;
    canvas.freeDrawingBrush.width = width;
  };

  const enableHighlight = () => {
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.color = color.replace(')', ',0.4)').replace('rgb','rgba');
    canvas.freeDrawingBrush.width = 20;
  };

  // Slidev의 per-slide drawing state 저장 방식 참고:
  // BroadcastChannel로 동일 파일 열린 다른 탭과 실시간 동기화 (Phase 3)
  const saveAnnotations = async () => {
    const json = canvas.toJSON(['id','_timestamp','_pageRatio']);
    await api.put(`/notes/${fileId}/${slideNum}/annotations`, json);
  };

  return { tool, setTool, color, setColor, width, setWidth,
           enablePen, enableHighlight, undo, redo, saveAnnotations };
}
```

> **참고**: Slidev는 `drauu` 라이브러리(SVG 기반)를 사용하지만, SlideNote는 이미지 위 픽셀 드로잉이 목적이므로 Canvas 기반 Fabric.js 유지. Undo 스택 패턴만 참고.

---

## Phase 2: 차별화 기능 (4~6주)

> **진행 상태**: ✅ 2-1 완료 (commit `bedfdde`, 2025-05)

### 2-1. AI 자동 요약 ✅

**구현 완료**:
- `services/gemini.py`: `summarize_slide(img_path)` — PRIMARY `gemini-2.5-flash-image`, FALLBACK `gemini-2.5-flash`, DELAY 7.0s
- `routers/ai.py`: `POST /api/ai/{file_id}/summarize` — 노트 파일 ai_summary 필드 업데이트
- `App.jsx`: "AI 요약 생성" 버튼 + 결과 우측 패널 표시, 방향키(←/→) 네비게이션, 헤더 UploadButton
- `.env.example`: `GOOGLE_API_KEY` 발급 안내

**원래 설계** (참고):
```
슬라이드 PNG + python-pptx 메타데이터 → Gemini Vision
                                            ↓
                                    한국어 요약 노트 (Markdown)
                                            ↓
                                    NoteEditor 우측에 자동 삽입
```

**핵심 프롬프트 전략** (gen_vision_improved.py의 SLIDE_PROMPT 응용):
- Mermaid 다이어그램 감지 → `graph TD`, `sequenceDiagram` 변환
- 테이블 → HTML table (colspan/rowspan 포함)
- 핵심 인사이트 3줄 요약 추가

### 2-2. 오디오 녹음 연동 ✅

**구현 완료** (commit `ed295ee`):
- `useAudioRecorder.js`: MediaRecorder WebM, `stamp(annotationId)` → elapsed 반환, `playFrom`, `loadAudio`
- `AudioPanel.jsx`: 녹음 시작/중지, 재생, 타임스탬프 목록 UI
- `routers/audio.py`: `POST /api/audio/{file_id}/{page}` (WebM 업로드), `PUT .../timestamps`, `GET .../file`
- `notes.py` Note 모델: `audio_url`, `audio_timestamps` 필드 추가
- `useAnnotation.js`: `stampRef` prop 연동 — `object:added` 시 녹음 중이면 elapsed 자동 기록 (`_timestamp`)
- `App.jsx`: `AudioPanel`, `stampRef` 연결

**원래 설계** (참고):
```
[녹음 시작] → MediaRecorder API
     │
     ▼
[필기 1 timestamp: 00:32]
[필기 2 timestamp: 01:15]  → annotation.json에 timestamp 저장
     │
     ▼
[필기 클릭] → audio.currentTime = timestamp → 재생
```

저장 구조:
```json
{
  "annotations": [...],
  "audio_url": "/uploads/{file_id}/audio/slide_{n}.webm",
  "audio_timestamps": {
    "annotation_id_1": 32.5,
    "annotation_id_2": 75.1
  }
}
```

### 2-3. 유인물 레이아웃 (PowerPoint '유인물 마스터' 대응) ✅

**구현 완료 (2026-05-03)**

**백엔드**
- `services/exporter.py` — `export_handout(slides_dir, notes_dir, out_path, layout)` 추가
  - `1up`: A4 1장에 슬라이드 1개 + 노트 8줄 영역
  - `2up`: A4 1장에 슬라이드 2개 + 각 노트 4줄 영역
  - `4up`: A4 1장에 슬라이드 4개 2×2 그리드 (요약 인쇄용, 슬라이드 번호 표시)
  - Pillow `ImageDraw`로 줄 그리기 + 한글 폰트(맑은 고딕) 지원, 없으면 기본 폰트 fallback
  - 노트 텍스트 자동 줄 바꿈 (`textwrap.wrap`)
- `routers/export.py` — `GET /api/export/{file_id}/handout?layout=1up|2up|4up` 추가
  - `_validate_id()` 헬퍼로 중복 검증 통합

**프론트엔드**
- `lib/api.js` — `downloadHandout(fileId, layout)` 추가 (a 태그 클릭 방식)
- `App.jsx` — 우측 패널 하단에 유인물 버튼 그룹 추가 (`1up` / `2up` / `4up`)

```python
# 실제 구현 시그니처
def export_handout(
    slides_dir: Path,
    notes_dir: Path,
    out_path: Path,
    layout: Literal["1up", "2up", "4up"] = "2up",
) -> Path:
```

### 2-4. 화이트보드 모드 ✅

**구현 완료 (2026-05-03)**

**백엔드**
- `routers/files.py` — `POST /api/files/{file_id}/whiteboard` 추가
  - 기존 슬라이드 크기 참조(없으면 1920×1080) → 흰 PNG 생성 → `page_NN.png` 저장
  - `metadata.json pageCount` 자동 증가
  - 반환: `{ page, url, pageCount }`

**프론트엔드**
- `store/useAppStore.js` — `setPageCount(pageCount)` 액션 추가
- `lib/api.js` — `insertWhiteboardPage(fileId)` 추가
- `components/SlideList.jsx`
  - 하단에 **"+ 빈 페이지 삽입"** 점선 버튼 추가
  - 삽입 후 해당 페이지로 자동 이동, `onWhiteboardInserted` 콜백 호출
- `components/SlideViewer.jsx`
  - `whiteboardPages: Set<number>` prop 수신
  - 화이트보드 페이지면 황색 안내 배너 표시: "✏ 화이트보드 페이지 — 자유롭게 드로잉하세요"
- `App.jsx`
  - `whiteboardPages` 상태 관리 (Set)
  - `SlideList`에 `onWhiteboardInserted` 전달, `SlideViewer`에 `whiteboardPages` 전달

**내보내기**: 화이트보드 페이지도 `page_NN.png`로 저장되므로 기존 `export_to_pdf` / `export_handout` 자동 포함

---

## Phase 3: 동기화 & 배포 (8주+)

> **진행 상태 (2026-05-03)**: Firebase 기본 동기화 구현 완료

### Firebase 연동 ✅ (부분 완료)

```
노트/주석 → Firestore (실시간 sync)  ✅
파일      → Firebase Storage          ⏳ (미구현)
인증      → Firebase Auth (Google)    ✅ (Console에서 공급자 활성화 필요)
```

**구현 완료**:
- Firebase 프로젝트: `slidenote-2026` (Tokyo 리전: `asia-northeast1`)
- 프로젝트 파일: `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`
- `src/frontend/src/lib/firebase.js` — `initializeApp`, `getFirestore`, `getAuth`
- `src/frontend/src/hooks/useAuth.js` — Google 팝업 로그인, `onAuthStateChanged`
- `src/frontend/src/hooks/useFirestore.js` — Firestore `setDoc` + `onSnapshot` 실시간 동기화
  - 문서 ID: `{uid}_{fileId}_{page}` 형태로 사용자·파일·페이지별 격리
- `App.jsx` 업데이트 — 헤더 Google 로그인 버튼, 노트 패널 `☁ 동기화` 상태 표시

**활성화 필요** (Firebase Console 수동):
```
https://console.firebase.google.com/project/slidenote-2026/authentication/providers
→ Google 공급자 활성화
```

**Firestore 보안 규칙** (`firestore.rules`):
```
notes/{noteId}   → uid 일치하는 로그인 사용자만 읽기/쓰기
sessions/{id}    → uid 일치하는 로그인 사용자만 읽기/쓰기
```

### Gotenberg 기반 PPTX 변환 서버 (Linux/Mac 배포 시)

> 참고: `gotenberg/gotenberg` — LibreOffice + Chromium 기반 문서 변환 API

```python
# services/converter.py — Linux 환경 PPTX 변환 대안
import httpx, pathlib

GOTENBERG_URL = os.getenv("GOTENBERG_URL", "http://gotenberg:3000")

async def pptx_to_pdf_via_gotenberg(pptx_path: pathlib.Path) -> bytes:
    """
    POST /forms/libreoffice/convert  (multipart)
    Gotenberg 주요 옵션:
      exportHiddenSlides=false  — 숨긴 슬라이드 제외
      exportNotesPages=false    — 발표자 노트 페이지 제외
      quality=90                — JPEG 품질
      reduceImageResolution=true / maxImageResolution=300
    반환: PDF bytes → 이후 PyMuPDF로 PNG 변환
    """
    async with httpx.AsyncClient() as client:
        files = {"files": (pptx_path.name, open(pptx_path, "rb"), "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        data  = {"exportHiddenSlides": "false", "quality": "90"}
        r = await client.post(f"{GOTENBERG_URL}/forms/libreoffice/convert", files=files, data=data)
        r.raise_for_status()
        return r.content
```

```yaml
# docker-compose.yml (Gotenberg 포함)
services:
  backend:
    build: ./src/backend
    ports: ["8000:8000"]
    volumes: ["./uploads:/app/uploads"]
    environment:
      - GOTENBERG_URL=http://gotenberg:3000
  frontend:
    build: ./src/frontend
    ports: ["5173:80"]
  gotenberg:
    image: gotenberg/gotenberg:8
    ports: ["3000:3000"]
    command:
      - "gotenberg"
      - "--libreoffice-auto-start=true"
```

> **주의**: Windows 로컬 개발 시는 win32com 사용. Linux 배포/CI 환경에서만 Gotenberg 활성화.

### 모바일 앱 (React Native, Phase 3 확장)

> 참고: `thatkid02/react-native-pdf-viewer` — NitroModules 기반 네이티브 PDF 뷰어

```tsx
// NitroModules 방식: 네이티브 PDF 렌더링 (pdfjs보다 성능 우수)
import { PdfViewer } from 'react-native-pdf-viewer';

// 핵심 Props (PdfViewer.nitro.ts 참고)
<PdfViewer
  source="file:///path/to/slide.pdf"  // file://, http://, https://
  horizontal={true}                   // iOS: 가로 스크롤 (슬라이드 모드)
  enablePaging={true}                 // iOS: 페이지 단위 스크롤
  spacing={8}
  onLoadComplete={(e) => setPageCount(e.pageCount)}
  onPageChange={(e) => setCurrentPage(e.page)}
  onThumbnailGenerated={(e) => setThumb(e.uri)}
/>
// DocumentInfo: { pageCount, pageWidth, pageHeight, currentPage }  (0-indexed)
// Android: PDF 렌더링은 PDFRenderer API 사용
```

> Flutter 대안: `aliyoge/flutter_file_preview` — Android(TBS), iOS(WKWebView)
> PPT/PDF/Word/Excel 지원. 단, 커스텀 주석 레이어 추가 어려움 → React Native 권장.

---

## 파일 저장 구조

```
uploads/
└── {file_id}/          # UUID
    ├── original.pptx   # 원본 파일
    ├── slides/
    │   ├── page_01.png
    │   ├── page_02.png
    │   └── ...
    ├── metadata.json    # 총 슬라이드 수, 파일명, 변환 시각
    ├── notes/
    │   ├── slide_01.json  # {text, annotations, ai_summary, audio_timestamps}
    │   └── slide_02.json
    └── audio/
        └── slide_01.webm
```

---

## 기술 리스크 & 대응

| 리스크 | 원인 | 대응 |
|--------|------|------|
| PPTX 변환 실패 | win32com은 Windows+PowerPoint 필수 | LibreOffice headless fallback |
| Gemini inline_data | flash-image가 디자인 슬라이드서 이미지 재생성 | flash 자동 폴백 (검증됨) |
| Rate limit | Gemini 무료 ~10 RPM | 7초 딜레이 + 큐 처리 |
| 대용량 PPTX | 21MB+ PPTX (22슬라이드) | 비동기 변환 + 진행률 SSE 스트리밍 |
| Canvas 성능 | Fabric.js 고해상도 Canvas | 뷰포트 크기만 렌더링, 스크롤 시 lazy load |

---

## 개발 우선순위 체크리스트

### 1주차
- [x] FastAPI 프로젝트 초기화
- [x] `converter.py`: `pdf_to_pngs()` 구현 (PyMuPDF)
- [x] `converter.py`: `pptx_to_pngs()` 구현 (win32com + LibreOffice fallback)
- [x] `/api/files/upload` 엔드포인트

### 2주차
- [x] React + Vite 프론트엔드 초기화
- [x] 3단 레이아웃 (`SlideList` + `SlideViewer` + `NoteEditor`)
- [x] Fabric.js Canvas 통합 (펜, 형광펜)
- [x] **Undo/Redo 스택 구현** (pympress scribble_list 패턴 — 스냅샷 방식, 최대 50단계)
- [x] **주석 좌표 정규화** (pdfanno `_pageRatio` 패턴 — 뷰포트 비율로 저장)
- [x] 노트 저장/불러오기 (`/api/notes`)

### 3주차
- [x] 주석 도구 (도형, 텍스트 박스)
- [x] PDF 내보내기 (주석 레이어 병합)
- [ ] 파일 목록 / 최근 파일 관리

### 4주차 (AI)
- [x] `gemini.py`: `call_gemini_smart()` 구현
- [x] `/api/ai/summarize` 엔드포인트
- [x] NoteEditor에 "AI 요약" 버튼 연동

### 5~6주차 (오디오)
- [x] MediaRecorder API 연동
- [x] 필기 timestamp 저장
- [x] 오디오 재생 컨트롤러

### 7~8주차 (유인물 & 화이트보드)
- [x] 유인물 레이아웃 PDF 내보내기 (1up/2up/4up + 한글 노트)
- [x] 화이트보드 빈 페이지 삽입 (`POST /api/files/{id}/whiteboard`)
- [x] Fabric.js 화이트보드 모드 (황색 배너, 자유 드로잉)

### 9~10주차 (Firebase 동기화)
- [x] Firebase 프로젝트 생성 (`slidenote-2026`, Tokyo 리전)
- [x] Firestore 데이터베이스 생성 + 보안 규칙 배포
- [x] Firebase SDK 설치 (`firebase` npm 패키지)
- [x] `lib/firebase.js` — `initializeApp`, `getFirestore`, `getAuth`
- [x] `hooks/useAuth.js` — Google 로그인/로그아웃, `onAuthStateChanged`
- [x] `hooks/useFirestore.js` — `setDoc` + `onSnapshot` 실시간 동기화
- [x] `App.jsx` — 헤더 로그인 버튼, 노트 패널 "☁ 동기화" 상태 표시
- [ ] Firebase Console에서 **Google 인증 공급자 활성화** (수동 필요)
  - https://console.firebase.google.com/project/slidenote-2026/authentication/providers
- [ ] Firebase Storage 연동 (파일 업로드 클라우드 저장)
- [ ] 다중 기기 세션 관리 (파일 ID → 사용자별 세션 저장)

---

## 오픈소스 참고 분석 요약

클론 위치: `repo/` (shallow, `--depth=1`)

| 리포지토리 | 핵심 분석 파일 | 채택한 패턴 |
|-----------|--------------|------------|
| `pdfanno` | `src/core/src/annotation/rect.js`, `schemas/pdfanno-schema.json` | 주석 좌표 정규화 (뷰포트 비율), uuid 기반 ID, type 체계 |
| `slidev` | `packages/client/composables/useDrawings.ts`, `state/drawings.ts` | Per-slide `Record<pageNo, svgStr>` 저장, BroadcastChannel 탭간 동기화 |
| `pympress` | `pympress/scribble.py` | Undo 스냅샷 스택 + Redo 스택, color/width 도구 상태 |
| `gotenberg` | `pkg/modules/libreoffice/routes.go` | `/forms/libreoffice/convert` multipart API, exportHiddenSlides/quality 옵션 |
| `PptxGenJS` | `README.md` | Phase 2: 유인물 내보내기 시 JS 환경에서 PPTX 재생성 고려 |
| `stirling-pdf` | `app/core/.../controller/api/` | 50+ PDF 도구 REST API 구조 참고 (Java Spring Boot) |
| `react-native-pdf-viewer` | `src/PdfViewer.nitro.ts` | NitroModules 인터페이스, DocumentInfo 이벤트 구조 |
| `flutter_file_preview` | README | Android TBS / iOS WKWebView, PPT/PDF 파일 지원 범위 |
| `loose-leaf` | iOS Obj-C | 제스처 기반 필기 UX 참고 (Apple Pencil pressure 값 저장 → pympress에서도 동일) |

### 핵심 채택 결정

1. **주석 좌표 정규화**: pdfanno의 `convertFromExportY()` 아이디어 → 저장 시 `_pageRatio:[w,h]` 기록, 로드 시 현재 뷰포트 크기로 역변환. 해상도 변경에도 주석 위치 유지.

2. **Undo/Redo 스택**: pympress의 `scribble_list` / `scribble_redo_list` 구조 → Fabric.js JSON 스냅샷 방식으로 구현 (최대 50단계, `path:create` 이벤트마다 저장).

3. **Gotenberg 백엔드 분리**: Windows는 win32com, Linux/Docker는 Gotenberg 선택적 사용. `GOTENBERG_URL` 환경변수로 활성화 여부 제어.

4. **모바일 우선순위**: react-native-pdf-viewer가 NitroModules 기반으로 성능 우수. Flutter는 주석 커스터마이징 제약 있어 React Native 우선.

---

## 참고 자료

- [PDF.js 공식](https://mozilla.github.io/pdf.js/)
- [Fabric.js 공식](http://fabricjs.com/)
- [drauu (Slidev 드로잉)](https://github.com/antfu/drauu)
- [PyMuPDF 문서](https://pymupdf.readthedocs.io/)
- [python-pptx 문서](https://python-pptx.readthedocs.io/)
- [google-genai SDK](https://googleapis.github.io/python-genai/)
- [Gotenberg 문서](https://gotenberg.dev/)
- 경쟁 앱: Slid, Notability, ExtraPPT Speaker Notes
