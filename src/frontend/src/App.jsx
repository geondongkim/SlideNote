import { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from './store/useAppStore'
import { uploadFile, fetchNote, summarizeSlide, downloadHandout, downloadNotesMarkdown, convertSlidesToMarkdown, downloadSlidesMarkdown, convertOriginalPdf, downloadOriginalPdf } from './lib/api'
import { useAudioRecorder } from './hooks/useAudioRecorder'
import { useAuth } from './hooks/useAuth'
import { useFirestore } from './hooks/useFirestore'
import { useStorage } from './hooks/useStorage'
import { useSession } from './hooks/useSession'
import UploadButton from './components/UploadButton'
import SlideList from './components/SlideList'
import SlideViewer from './components/SlideViewer'
import AudioPanel from './components/AudioPanel'
import RecentFiles from './components/RecentFiles'
import PresentationMode from './components/PresentationMode'

export default function App() {
  const { fileId, currentSlide, pageCount, setCurrentSlide, filename, setFile, clearFile } = useAppStore()
  const [noteText, setNoteText] = useState('')
  const [aiSummary, setAiSummary] = useState('')
  const [summarizing, setSummarizing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [whiteboardPages, setWhiteboardPages] = useState(new Set())
  const [presenting, setPresenting] = useState(false)
  const [converting, setConverting] = useState(false)
  const [convertProgress, setConvertProgress] = useState({ page: 0, total: 0 })
  const [convertFilename, setConvertFilename] = useState('')
  const [activeTab, setActiveTab] = useState('note')
  const [dragOver, setDragOver] = useState(false)
  const [hqPdfState, setHqPdfState] = useState('idle') // 'idle' | 'converting' | 'done' | 'error'
  const [hqPdfMsg, setHqPdfMsg] = useState('')
  const persistRef = useRef(null)
  const stampRef = useRef(null)
  const setToolRef = useRef(null)

  // Firebase Auth
  const { user, loading: authLoading, login, logout } = useAuth()

  // Firebase Storage + Firestore Session
  const { uploadToStorage } = useStorage(user?.uid ?? null)
  const { saveSession } = useSession(user?.uid ?? null)

  // 파일 업로드 성공 콜백 — Storage + Firestore 세션 저장
  const handleUploadSuccess = useCallback(
    async (file, meta) => {
      if (!user) return
      const storageUrl = await uploadToStorage(file, meta.fileId).catch(() => null)
      await saveSession({
        fileId: meta.fileId,
        filename: meta.filename,
        pageCount: meta.pageCount,
        ext: meta.ext,
        ...(storageUrl ? { storageUrl } : {}),
      })
    },
    [user, uploadToStorage, saveSession]
  )

  // RecentFiles 빈 상태 CTA에서 직접 업로드
  const handleRecentUpload = useCallback(
    async (file, meta) => {
      if (!user) return
      await handleUploadSuccess(file, meta)
    },
    [user, handleUploadSuccess]
  )

  // Firestore 원격 업데이트 수신 (다른 기기에서 변경됐을 때)
  const handleRemoteUpdate = useCallback((text, _annotations) => {
    setNoteText((prev) => (prev !== text ? text : prev))
  }, [])

  const { syncNote } = useFirestore(
    user?.uid ?? null,
    fileId,
    currentSlide,
    handleRemoteUpdate
  )

  const audio = useAudioRecorder(fileId, currentSlide)
  // stampRef를 통해 useAnnotation이 녹음 중 시점을 기록
  stampRef.current = audio.recording ? audio.stamp : null

  // 슬라이드 변경 시 노트 + AI 요약 로드
  useEffect(() => {
    if (!fileId) return
    fetchNote(fileId, currentSlide).then((n) => {
      setNoteText(n.text || '')
      setAiSummary(n.ai_summary || '')
    })
  }, [fileId, currentSlide])

  // 키보드 네비게이션 ←/→ + 도구 단축키 V/P/H/T/A
  const TOOL_SHORTCUTS = { v: 'select', p: 'pen', h: 'highlight', e: 'eraser', t: 'text', a: 'arrow' }
  useEffect(() => {
    const handler = (e) => {
      if (!fileId) return
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return
      if (e.key === 'ArrowRight' && currentSlide < pageCount)
        setCurrentSlide(currentSlide + 1)
      if (e.key === 'ArrowLeft' && currentSlide > 1)
        setCurrentSlide(currentSlide - 1)
      if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        const key = e.key.toLowerCase()
        if (TOOL_SHORTCUTS[key]) setToolRef.current?.(TOOL_SHORTCUTS[key])
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [fileId, currentSlide, pageCount, setCurrentSlide])

  // AI 요약 요청 (발표자 노트 형식 — 3줄 핵심 요약)
  const handleSummarize = async () => {
    if (!fileId || summarizing) return
    setSummarizing(true)
    try {
      const { summary } = await summarizeSlide(fileId, currentSlide)
      setAiSummary(summary)
    } catch (e) {
      setAiSummary(`오류: ${e.response?.data?.detail || e.message}`)
    } finally {
      setSummarizing(false)
    }
  }

  // 슬라이드 → Markdown 변환 (원문 충실 변환 — AI 요약과 다른 기능)
  const handleConvertToMarkdown = async () => {
    if (!fileId || converting) return
    setConverting(true)
    setConvertProgress({ page: 0, total: 0 })
    try {
      await convertSlidesToMarkdown(fileId, (state) => {
        if (state.filename) setConvertFilename(state.filename)
        if (state.total) setConvertProgress((p) => ({ ...p, total: state.total }))
        if (state.page) setConvertProgress((p) => ({ ...p, page: state.page }))
      })
      // 변환 완료 → 바로 다운로드
      downloadSlidesMarkdown(fileId, convertFilename || fileId)
    } catch (e) {
      alert(`Markdown 변환 오류: ${e.message}`)
    } finally {
      setConverting(false)
    }
  }

  // 고품질 PPTX → PDF 변환 (벡터/폰트/하이퍼링크 보존)
  const handleHqPdf = async () => {
    if (!fileId || hqPdfState === 'converting') return
    setHqPdfState('converting')
    setHqPdfMsg('PDF 변환 중…')
    try {
      await convertOriginalPdf(fileId, (state) => {
        setHqPdfMsg(state.message || '')
        if (state.status === 'done') setHqPdfState('done')
        if (state.status === 'error') setHqPdfState('error')
      })
      // 변환 완료 시 자동 다운로드
      const stem = filename ? filename.replace(/\.[^.]+$/, '') : fileId
      downloadOriginalPdf(fileId, stem)
      // 3초 후 상태 초기화
      setTimeout(() => setHqPdfState('idle'), 3000)
    } catch (e) {
      setHqPdfMsg(e.message)
      setHqPdfState('error')
      setTimeout(() => setHqPdfState('idle'), 4000)
    }
  }

  // 노트 텍스트 디바운스 자동 저장 (주석은 persistRef로) + Firestore 동기화
  useEffect(() => {
    if (!fileId) return
    const t = setTimeout(async () => {
      setSaving(true)
      try {
        if (persistRef.current) {
          await persistRef.current(noteText)
        }
        // 로그인 상태일 때만 Firestore에도 동기화
        if (user) {
          await syncNote(noteText, {})
        }
      } finally {
        setSaving(false)
      }
    }, 500)
    return () => clearTimeout(t)
  }, [noteText, fileId, currentSlide, user, syncNote])

  // 드래그 앤 드롭 업로드
  const handleDragOver = (e) => {
    e.preventDefault()
    const hasFile = Array.from(e.dataTransfer.items).some((item) => item.kind === 'file')
    if (hasFile) setDragOver(true)
  }
  const handleDragLeave = (e) => {
    if (!e.relatedTarget || !e.currentTarget.contains(e.relatedTarget)) setDragOver(false)
  }
  const handleDrop = async (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    const ext = file.name.split('.').pop().toLowerCase()
    if (!['pdf', 'pptx'].includes(ext)) { alert('PPTX 또는 PDF 파일만 업로드 가능합니다.'); return }
    try {
      const meta = await uploadFile(file)
      setFile(meta.fileId, meta.pageCount, meta.filename ?? '')
      if (user) await handleUploadSuccess(file, meta)
    } catch (err) {
      alert(`업로드 오류: ${err.message}`)
    }
  }

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* 드래그 오버레이 */}
      {dragOver && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-blue-950/80 pointer-events-none border-4 border-blue-400 border-dashed">
          <div className="text-center">
            <p className="text-5xl mb-3">📂</p>
            <p className="text-white text-xl font-bold">PPTX / PDF 파일을 드롭하세요</p>
          </div>
        </div>
      )}
      {/* 발표 모드 오버레이 */}
      {presenting && (
        <PresentationMode onExit={() => setPresenting(false)} />
      )}
      {/* 헤더 */}
      <header className="flex items-center justify-between px-4 py-2 bg-gray-950 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={clearFile}
            className="font-semibold text-white text-sm shrink-0 hover:text-blue-400 transition-colors"
          >SlideNote</button>
          {filename && (
            <span className="text-gray-400 text-xs truncate max-w-[200px]" title={filename}>
              / {filename}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {fileId && (
            <span className="text-xs text-gray-400">
              {currentSlide} / {pageCount}
            </span>
          )}
          {/* Firebase Auth 상태 */}
          {!authLoading && (
            user ? (
              <div className="flex items-center gap-2">
                <img
                  src={user.photoURL}
                  alt={user.displayName}
                  className="w-6 h-6 rounded-full"
                />
                <span className="text-xs text-gray-300 max-w-[100px] truncate">
                  {user.displayName}
                </span>
                <button
                  onClick={logout}
                  className="text-xs text-gray-400 hover:text-white transition-colors"
                >
                  로그아웃
                </button>
              </div>
            ) : (
              <button
                onClick={login}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
              >
                Google 로그인
              </button>
            )
          )}
          <UploadButton onSuccess={handleUploadSuccess} />
          {fileId && (
            <button
              onClick={() => setPresenting(true)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 hover:bg-green-700 text-white rounded transition-colors"
              title="발표 모드 시작"
            >
              ▶ 발표
            </button>
          )}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-48 bg-gray-900 border-r border-gray-700 overflow-y-auto p-2 shrink-0">
          <SlideList
            onWhiteboardInserted={(page) =>
              setWhiteboardPages((prev) => new Set([...prev, page]))
            }
          />
        </aside>

        {fileId ? (
          <SlideViewer
            persistRef={persistRef}
            stampRef={stampRef}
            setToolRef={setToolRef}
            whiteboardPages={whiteboardPages}
          />
        ) : (
          <main className="flex-1 bg-gray-800 overflow-y-auto">
            <RecentFiles onUpload={handleRecentUpload} />
          </main>
        )}

        <aside className="w-80 bg-gray-900 border-l border-gray-700 flex flex-col shrink-0">
          {/* 탭 헤더 */}
          <div className="flex shrink-0 border-b border-gray-700">
            {[
              { id: 'note',   label: '노트' },
              { id: 'export', label: '내보내기' },
              { id: 'audio',  label: '오디오' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 text-xs font-medium relative transition-colors ${
                  activeTab === tab.id
                    ? 'text-white border-b-2 border-blue-500'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* 노트 탭 */}
          {activeTab === 'note' && (
            <div className="flex flex-col flex-1 overflow-hidden p-4">
              <div className="flex justify-between items-center mb-2">
                <h2 className="text-sm font-semibold text-gray-300">노트 ({currentSlide}페이지)</h2>
                <div className="flex items-center gap-1">
                  {user && <span className="text-[10px] text-blue-400">☁ 동기화</span>}
                  <span className="text-[10px] text-gray-500">{saving ? '저장 중…' : '자동 저장'}</span>
                </div>
              </div>
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                disabled={!fileId}
                className="flex-1 bg-gray-800 text-gray-200 text-sm p-2 rounded resize-none border border-gray-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                placeholder="발표 대본이나 메모를 입력하세요..."
              />
              {aiSummary && (
                <div className="mt-3 p-2 rounded bg-gray-800 border border-gray-600">
                  <p className="text-[10px] text-blue-400 mb-1 font-medium">AI 요약</p>
                  <p className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">{aiSummary}</p>
                </div>
              )}
              <button
                onClick={handleSummarize}
                disabled={!fileId || summarizing}
                className="mt-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white text-sm py-1 rounded transition-colors"
              >
                {summarizing ? 'AI 요약 생성 중…' : 'AI 요약 생성'}
              </button>
            </div>
          )}

          {/* 내보내기 탭 */}
          {activeTab === 'export' && (
            <div className="flex flex-col flex-1 overflow-y-auto p-4 gap-1">
              {fileId ? (
                <>
                  <a
                    href={`/api/export/${fileId}`}
                    download
                    className="block text-center bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm py-1 rounded"
                  >
                    PDF 내보내기
                  </a>
                  <div className="flex gap-1 items-center">
                    <span className="text-[10px] text-gray-500 shrink-0">유인물</span>
                    {['1up', '2up', '4up'].map((layout) => (
                      <button
                        key={layout}
                        onClick={() => downloadHandout(fileId, layout)}
                        className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs py-1 rounded"
                      >
                        {layout}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => downloadNotesMarkdown(fileId)}
                    className="block w-full text-center bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm py-1 rounded"
                  >
                    📝 노트 Markdown 내보내기
                  </button>
                  <div className="mt-1 border-t border-gray-700 pt-2">
                    <p className="text-[10px] text-emerald-400 mb-1 font-medium">
                      슬라이드 원문 → Markdown <span className="text-gray-500">(AI 요약 아님)</span>
                    </p>
                    <button
                      onClick={handleConvertToMarkdown}
                      disabled={!fileId || converting}
                      className="w-full bg-emerald-700 hover:bg-emerald-600 disabled:bg-gray-600 text-white text-sm py-1 rounded transition-colors"
                    >
                      {converting
                        ? `변환 중… (${convertProgress.page}/${convertProgress.total})`
                        : '📄 슬라이드 Markdown 변환'}
                    </button>
                    {converting && convertProgress.total > 0 && (
                      <div className="mt-1 w-full bg-gray-700 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.round((convertProgress.page / convertProgress.total) * 100)}%` }}
                        />
                      </div>
                    )}
                    <p className="text-[9px] text-gray-500 mt-1 leading-snug">
                      Obsidian · Notion · NotebookLM 최적화<br />
                      표·다이어그램·텍스트 원문 보존
                    </p>
                  </div>
                  <div className="mt-1 border-t border-gray-700 pt-2">
                    <p className="text-[10px] text-amber-400 mb-1 font-medium flex items-center gap-1">
                      ✦ 원본 품질 PDF
                      <span className="text-gray-500 font-normal">벡터·폰트·링크 보존</span>
                    </p>
                    <button
                      onClick={handleHqPdf}
                      disabled={!fileId || hqPdfState === 'converting'}
                      className={`w-full text-sm py-1 rounded transition-colors font-medium ${
                        hqPdfState === 'done'
                          ? 'bg-green-700 text-green-100'
                          : hqPdfState === 'error'
                          ? 'bg-red-800 text-red-200'
                          : hqPdfState === 'converting'
                          ? 'bg-amber-800 text-amber-200 cursor-wait'
                          : 'bg-amber-700 hover:bg-amber-600 text-white'
                      }`}
                    >
                      {hqPdfState === 'converting' && (
                        <span className="inline-block mr-1 animate-spin">◌</span>
                      )}
                      {hqPdfState === 'done' && '✓ 다운로드 완료'}
                      {hqPdfState === 'error' && '✗ 변환 실패'}
                      {hqPdfState === 'converting' && '변환 중…'}
                      {hqPdfState === 'idle' && '📥 원본 품질로 저장'}
                    </button>
                    {(hqPdfState === 'converting' || hqPdfState === 'error') && hqPdfMsg && (
                      <p className={`text-[9px] mt-1 leading-snug ${hqPdfState === 'error' ? 'text-red-400' : 'text-amber-400'}`}>
                        {hqPdfMsg}
                      </p>
                    )}
                    <p className="text-[9px] text-gray-500 mt-1 leading-snug">
                      Windows: PowerPoint COM (최고 품질)<br />
                      Linux: LibreOffice / Gotenberg
                    </p>
                  </div>
                </>
              ) : (
                <p className="text-xs text-gray-500 text-center mt-4">파일을 먼저 열어주세요</p>
              )}
            </div>
          )}

          {/* 오디오 탭 */}
          {activeTab === 'audio' && (
            <div className="flex flex-col flex-1 overflow-y-auto p-4">
              {fileId ? (
                <AudioPanel />
              ) : (
                <p className="text-xs text-gray-500 text-center mt-4">파일을 먼저 열어주세요</p>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
