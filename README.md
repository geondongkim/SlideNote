# SlideNote

> PPTX / PDF 혼용 슬라이드 노트 앱 — 주석·필기·AI 요약·오디오 연동

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 개요

발표자, 학생, 강연 청중 모두를 위한 **슬라이드 노트 작성 앱**입니다.  
PPTX와 PDF를 자유롭게 불러와 슬라이드 위에 직접 주석을 달고, 발표 대본을 작성하며, AI 요약과 오디오 연동 기능을 제공합니다.

```
[슬라이드 목록] ─── [슬라이드 뷰어 + 주석] ─── [노트/대본/AI 요약]
```

---

## 주요 기능

### MVP (1단계)

| 기능 | 설명 |
|------|------|
| **파일 불러오기** | PPTX / PDF 업로드 → 고해상도 PNG로 자동 변환 |
| **슬라이드 뷰어** | PDF.js 기반 고품질 렌더링, 확대/축소/이동 |
| **슬라이드별 노트** | 각 슬라이드 하단에 발표 대본 텍스트 영역 |
| **주석 및 필기** | 펜·형광펜·도형·텍스트 박스 (Fabric.js Canvas) |
| **3단 레이아웃** | 좌(목록) / 중(뷰어+주석) / 우(노트) |
| **PDF 내보내기** | 주석 + 노트를 합쳐 PDF 저장 |

### 차별화 기능 (2단계)

| 기능 | 설명 |
|------|------|
| **AI 자동 요약** | Gemini Vision API로 슬라이드 내용 → 한국어 요약 노트 자동 생성 |
| **오디오 녹음 연동** | 필기 시점 오디오 녹음 → 필기 클릭 시 해당 시점 재생 |
| **화이트보드 모드** | 슬라이드 사이 빈 드로잉 페이지 삽입 |
| **유인물 레이아웃** | 1슬라이드/2슬라이드 per 페이지 인쇄 배치 옵션 |
| **실시간 동기화** | Firebase Firestore로 기기 간 노트 공유 |

---

## 기술 스택

### 백엔드 (Python)

```
FastAPI 0.115          — REST API 서버
PyMuPDF (fitz) 1.27    — PDF → PNG 변환 (150 DPI)
python-pptx 1.0        — PPTX 메타데이터·텍스트 추출
pywin32 / LibreOffice  — PPTX → PDF 변환
google-genai           — Gemini Vision API (AI 요약)
Pillow 12              — 이미지 처리
python-dotenv          — 환경 변수 관리
```

### 프론트엔드 (React)

```
React 18 + Vite        — SPA 프레임워크
PDF.js (pdfjs-dist)    — 브라우저 PDF 렌더링
Fabric.js 6            — Canvas 주석·필기 엔진
TailwindCSS 3          — UI 스타일링
Zustand                — 상태 관리
React Query            — 서버 상태 동기화
```

### 인프라

```
Firebase Firestore      — 실시간 노트 동기화 (2단계)
Firebase Storage        — 파일 저장 (2단계)
Docker + docker-compose — 로컬 개발 환경
```

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Node.js 20+
- (선택) PowerPoint 설치 — PPTX 고품질 변환 시 필요

### 1. 저장소 클론

```bash
git clone https://github.com/geondongkim/SlideNote.git
cd SlideNote
```

### 2. 백엔드 실행

```bash
cd src/backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# .env 파일 생성
echo "GOOGLE_API_KEY=your_gemini_key" > .env

uvicorn main:app --reload --port 8000
```

### 3. 프론트엔드 실행

```bash
cd src/frontend
npm install
npm run dev
# http://localhost:5173 에서 접속
```

---

## 프로젝트 구조

```
SlideNote/
├── README.md
├── docs/
│   ├── implementation_plan.md   # 단계별 구현 계획
│   ├── architecture.md          # 시스템 아키텍처
│   └── troubleshooting.md       # 트러블슈팅 & 노하우
├── src/
│   ├── backend/
│   │   ├── main.py              # FastAPI 앱 진입점
│   │   ├── routers/
│   │   │   ├── files.py         # 파일 업로드/변환 API
│   │   │   ├── notes.py         # 노트 CRUD API
│   │   │   └── ai.py            # AI 요약 API
│   │   ├── services/
│   │   │   ├── converter.py     # PPTX/PDF → PNG 변환
│   │   │   ├── gemini.py        # Gemini Vision 연동
│   │   │   └── exporter.py      # PDF 내보내기
│   │   └── requirements.txt
│   └── frontend/
│       ├── index.html
│       ├── package.json
│       ├── vite.config.js
│       └── src/
│           ├── App.jsx
│           ├── components/
│           │   ├── SlideList.jsx      # 좌측 슬라이드 목록
│           │   ├── SlideViewer.jsx    # 중앙 뷰어 + Canvas
│           │   ├── NoteEditor.jsx     # 우측 노트 에디터
│           │   └── Toolbar.jsx        # 주석 도구 모음
│           ├── stores/
│           │   └── slideStore.js      # Zustand 전역 상태
│           └── hooks/
│               ├── usePdfRenderer.js  # PDF.js 훅
│               └── useAnnotation.js   # Fabric.js 훅
└── scripts/
    ├── setup.sh                 # 초기 환경 세팅
    └── dev.sh                   # 개발 서버 일괄 실행
```

---

## API 엔드포인트 (백엔드)

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/files/upload` | PPTX/PDF 업로드 → 슬라이드 PNG 생성 |
| `GET` | `/api/files` | 업로드된 파일 목록 (최신순) |
| `GET` | `/api/files/{file_id}` | 파일 메타데이터 조회 |
| `DELETE` | `/api/files/{file_id}` | 파일 삭제 |
| `GET` | `/api/files/{file_id}/slides` | 슬라이드 목록 반환 |
| `GET` | `/api/notes/{file_id}/{page}` | 특정 슬라이드 노트 조회 |
| `PUT` | `/api/notes/{file_id}/{page}` | 노트 + 주석 저장 |
| `POST` | `/api/ai/{file_id}/summarize` | AI 요약 생성 (Gemini Vision) |
| `POST` | `/api/audio/{file_id}/{page}` | 오디오 WebM 업로드 |
| `PUT` | `/api/audio/{file_id}/{page}/timestamps` | 주석 시점 저장 |
| `GET` | `/api/audio/{file_id}/{page}/file` | 오디오 스트리밍 반환 |
| `GET` | `/api/export/{file_id}` | 슬라이드 PDF 내보내기 |
| `GET` | `/api/export/{file_id}/handout?layout=2up` | 유인물 레이아웃 PDF (1up/2up/4up) |
| `POST` | `/api/files/{file_id}/whiteboard` | 빈 페이지 삽입 (화이트보드) |

---

## 알려진 제약사항 & 노하우

> 이 프로젝트는 PPTX/PDF → Markdown 변환 파이프라인 개발 경험을 바탕으로 설계되었습니다.  
> 자세한 내용은 [docs/troubleshooting.md](docs/troubleshooting.md)를 참조하세요.

- **PPTX → PNG 변환**: Windows에서 `pywin32` (PowerPoint COM) 사용 시 고품질 출력 가능. Linux/Mac은 LibreOffice headless 사용
- **gemini-2.5-flash-image** 모델은 복잡 다이어그램이나 비즈니스 디자인 슬라이드에서 inline_data(이미지 재생성) 시도 → `gemini-2.5-flash` 폴백 필수
- **Rate limit**: Gemini 무료 티어 ~10 RPM → 배치 요청 시 7초 딜레이 적용
- **PDF 렌더링**: DPI 150이 속도/품질 최적 균형점 (300 DPI는 2~3배 느림)
- **PPTX 메타데이터**: python-pptx로 텍스트·테이블 구조를 미리 추출하여 AI 프롬프트에 보강하면 인식률 향상

---

## 로드맵

- [x] **v0.1** — PDF/PPTX 업로드 + 슬라이드 뷰어 + 노트 저장
- [x] **v0.2** — Fabric.js 주석 레이어 (펜·형광펜·텍스트)
- [x] **v0.3** — AI 자동 요약 (Gemini Vision) + 방향키 네비게이션 + 헤더 업로드
- [x] **v0.4** — 오디오 녹음 연동 (MediaRecorder + 주석 timestamp)
- [x] **v0.5** — 유인물 레이아웃 PDF (1up/2up/4up, 노트 포함)
- [x] **v1.0** — 화이트보드 모드 (빈 페이지 삽입 + Fabric.js 자유 드로잉)
- [x] **v1.1** — Firebase 동기화 (Google 로그인 + Firestore 실시간 노트 동기화)
  > Google Auth 공급자 활성화 필요: https://console.firebase.google.com/project/slidenote-2026/authentication/providers
- [x] **v1.2** — 파일 목록/삭제 + Firebase Storage + Firestore 세션 관리 (useSession.js, useStorage.js)
  > Firebase Storage 활성화 필요: https://console.firebase.google.com/project/slidenote-2026/storage

---

## 라이선스

MIT License © 2026 geondongkim
