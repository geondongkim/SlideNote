# SlideNote — GitHub Copilot 지침

> 이 파일은 리포지토리 전체에 적용되는 **시스템 프롬프트** 역할을 합니다.
> Copilot은 모든 답변·코드 생성 시 아래 규칙을 따릅니다.
>
> **출처**: [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) (CLAUDE.md 작성법) +
> [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (Karpathy 4원칙).
> 200줄 미만 유지 (베스트 프랙티스 권장).

---

## 1. 프로젝트 개요

**SlideNote** — PPTX/PDF 혼용 슬라이드 노트 웹 앱. 슬라이드 위에 필기·주석·AI 요약을 추가하고, 주석 포함 PDF로 내보냅니다.

- **백엔드**: FastAPI 0.115 + Python 3.13 (`src/backend/`)
- **프론트엔드**: React 18 + Vite 6 + Fabric.js 6 + TailwindCSS 3 (`src/frontend/`)
- **변환**: PyMuPDF (PDF), pywin32 (Windows PPTX), Gotenberg (Linux 폴백)
- **AI**: google-genai (Gemini 2.5 Vision)
- **개발 환경**: Windows + PowerShell (1차 타겟)

상세 계획: [docs/implementation_plan.md](../docs/implementation_plan.md) | 노하우: [docs/troubleshooting.md](../docs/troubleshooting.md)

---

## 2. Karpathy 4원칙 (코드 생성 핵심 규칙)

### (1) Think Before Coding — 가정을 표면화하라
- 요청이 모호하면 **추측하지 말고 질문**한다. 여러 해석이 가능하면 모두 제시한다.
- 더 간단한 접근이 있으면 그렇게 말하고, 정당한 경우 사용자 의견에 반박한다.

### (2) Simplicity First — 요청한 것만 만들어라
- 요청 범위를 넘어선 기능·추상화·"유연성"을 추가하지 않는다.
- 일회성 코드를 위한 헬퍼/추상화 금지. 발생할 수 없는 시나리오를 위한 에러 처리 금지.
- 200줄로 짠 것을 50줄로 줄일 수 있으면 다시 짠다.
- 시니어 엔지니어가 "과도하게 복잡하다"고 할지 자문한다.

### (3) Surgical Changes — 요청에 직접 매핑되는 변경만
- 인접 코드·주석·포맷을 "개선"하지 않는다.
- 망가지지 않은 것을 리팩터링하지 않는다.
- 변경 라인은 모두 사용자 요청으로 추적 가능해야 한다.
- 손대지 않은 코드에 docstring/타입/주석을 임의로 추가하지 않는다.
- 미사용 import/변수는 **내가 만든 것만** 정리한다. 기존 dead code는 언급만 하고 지우지 않는다.

### (4) Goal-Driven Execution — 검증 가능한 성공 기준
- "검증 만들기" → "잘못된 입력에 대한 테스트 작성 → 통과시키기"
- "버그 수정" → "재현 테스트 작성 → 통과시키기"
- 다단계 작업은 단계별 검증 체크와 함께 짧은 계획을 먼저 제시한다.

---

## 3. SlideNote 코딩 컨벤션

### 3-1. Python (백엔드)

- **포매터**: black (line-length=100), isort (profile=black). PEP 8 준수.
- **타입 힌트 필수**: 새 함수·메서드는 모든 인자/반환 타입 명시. `from __future__ import annotations` 권장.
- **경로**: `pathlib.Path` 사용. 문자열 경로 금지.
- **로깅**: `print()` 금지 → `logging.getLogger(__name__)`. 단, 검증된 변환 스크립트(`gen_vision_*.py`)의 진행 출력은 예외.
- **비동기**: I/O 바운드 엔드포인트는 `async def`. `httpx.AsyncClient` 사용.
- **Pydantic v2** 사용 (FastAPI 0.115 기본).

### 3-2. JavaScript / React (프론트엔드)

- **컴포넌트**: 함수형 + Hooks. 클래스 컴포넌트 금지.
- **파일명**: 컴포넌트는 `PascalCase.jsx`, 훅은 `useXxx.js`, 유틸은 `camelCase.js`.
- **상태**: 로컬은 `useState` / `useReducer`, 전역은 Zustand. Context API 남용 금지.
- **서버 상태**: `@tanstack/react-query` 사용. 직접 `useEffect` + fetch 패턴 금지.
- **스타일**: TailwindCSS 유틸리티 우선. `index.css`에는 `@layer` 변수만.
- **API 호출**: `axios` 인스턴스(`src/api.js`) 경유. `fetch` 직접 호출 금지.

### 3-3. 주석 데이터 스키마 (변경 금지)

```jsonc
{
  "version": "1.0",
  "page": 1,                          // 1-based (pdfanno 호환)
  "annotations": {
    "fabricVersion": "6.6.1",
    "objects": [{
      "id": "<uuid>",                 // 필수
      "_pageRatio": [w, h],           // 저장 당시 뷰포트 (해상도 무관 위치 복원)
      "_timestamp": 32.5,             // 오디오 재생 시각 (Phase 2)
      "type": "path|rect|text"        // ...Fabric.js 표준 필드
    }]
  }
}
```
- `id`, `_pageRatio` 필드는 **모든 주석 객체에 필수**. Fabric `toJSON(['id','_pageRatio','_timestamp'])`로 직렬화.

---

## 4. 검증된 매직 넘버 (변경 시 사유 필수)

기존 PPTX/PDF→Markdown 파이프라인에서 **실측 검증된 값**입니다. 함부로 바꾸지 않습니다.

| 값 | 의미 | 출처 |
|----|------|------|
| `DPI = 150` | PyMuPDF PDF→PNG 해상도 (속도/품질 최적) | gen_vision_improved.py |
| `PNG_WIDTH = 1920` | win32com PPTX→PNG 가로 픽셀 | troubleshooting.md §1 |
| `GEMINI_DELAY = 7.0` | Gemini 무료 티어 ~10 RPM 대응 | troubleshooting.md §3 |
| `GEMINI_PRIMARY = "gemini-2.5-flash-image"` → `FALLBACK = "gemini-2.5-flash"` | inline_data 응답 시 자동 폴백 | troubleshooting.md §3 |
| Undo 스택 최대 50단계 | 메모리/UX 균형 | implementation_plan.md (pympress 패턴) |

---

## 5. 환경별 주의사항

### Windows + PowerShell (1차 개발 환경)
- 명령 체이닝: `;` 사용. **`&&` 사용 금지** (PowerShell 5.1 미지원).
- `2>&1` 리다이렉션은 stderr 출력만 있어도 exit code 1 반환. **종료 메시지 텍스트로 성공 여부 판단**.
- win32com 사용 시: PowerPoint COM은 `Visible=True` 필수, 슬라이드 인덱스는 **1-based**, `prs.Slides`는 `list()` 변환 후 사용.

### 한글 경로
- 작업 폴더에 한글이 포함됨 (`학습자료/`). 모든 파일 I/O는 `pathlib.Path` + `encoding='utf-8'` 명시.

---

## 6. 빌드/실행 명령

```powershell
# 개발 서버 (백엔드 + 프론트엔드 동시 실행)
bash scripts/dev.sh

# 백엔드 단독
cd src/backend; uvicorn main:app --reload --port 8000

# 프론트엔드 단독
cd src/frontend; npm run dev      # vite :5173

# 백엔드 의존성 설치
pip install -r src/backend/requirements.txt

# 프론트엔드 의존성 설치
cd src/frontend; npm install
```

---

## 7. Git 커밋 규칙

- **Conventional Commits** 형식: `<type>: <subject>` (`feat`, `fix`, `docs`, `refactor`, `chore`, `test`).
- 본문은 `- 항목` 불릿으로 구체적 변경 사항 나열.
- 커밋 메시지·코드 주석·문서: **한국어**.
- 작업 단위 완료 시 자동으로 `git commit && git push` 수행 (사용자 별도 지시 없어도).
- 대규모 변경은 파일/관심사별로 분리 커밋 (claude-code-best-practice CLAUDE.md §"Git Commit Rules" 참고).

---

## 8. 파일 작업 우선순위

1. **편집 > 생성**: 기존 파일을 수정할 수 있으면 새 파일 만들지 않는다.
2. **변경 문서화 마크다운 파일을 임의로 만들지 않는다** (사용자가 명시적으로 요청한 경우 제외).
3. `docs/` 업데이트는 작업 완료 시 항상 동반 (implementation_plan.md, troubleshooting.md, README.md).
4. `.env`, `uploads/`, `node_modules/`, `repo/` 는 절대 커밋 금지 (.gitignore 확인).

---

## 9. 보안

- API 키(`GEMINI_API_KEY` 등)는 `.env`만. 코드/문서/커밋 메시지에 노출 금지.
- 사용자 업로드 파일: 파일명 sanitize, MIME 검증, 사이즈 제한(50MB) 적용.
- OWASP Top 10 항목(특히 Path Traversal, SSRF, XSS) 점검.

---

## 10. 참고 자료

- 오픈소스 분석: `repo/` 폴더 (gitignored, 로컬 전용 — pdfanno, slidev, pympress, gotenberg 등 9개)
- 검증 스크립트: `../15_AzureVM을 활용한 SQLServer_0429-0513(이정환)/gen_vision_improved.py`
- 기술 결정 근거: [docs/implementation_plan.md](../docs/implementation_plan.md)
