import { useEffect, useRef, useState } from 'react'
import { useAppStore } from './store/useAppStore'
import { fetchNote, summarizeSlide, downloadHandout } from './lib/api'
import { useAudioRecorder } from './hooks/useAudioRecorder'
import UploadButton from './components/UploadButton'
import SlideList from './components/SlideList'
import SlideViewer from './components/SlideViewer'
import AudioPanel from './components/AudioPanel'

export default function App() {
  const { fileId, currentSlide, pageCount, setCurrentSlide } = useAppStore()
  const [noteText, setNoteText] = useState('')
  const [aiSummary, setAiSummary] = useState('')
  const [summarizing, setSummarizing] = useState(false)
  const [saving, setSaving] = useState(false)
  const persistRef = useRef(null)
  const stampRef = useRef(null)   // useAudioRecorder.stamp → useAnnotation

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

  // 키보드 네비게이션 ←/→
  useEffect(() => {
    const handler = (e) => {
      if (!fileId) return
      if (e.target.tagName === 'TEXTAREA') return
      if (e.key === 'ArrowRight' && currentSlide < pageCount)
        setCurrentSlide(currentSlide + 1)
      if (e.key === 'ArrowLeft' && currentSlide > 1)
        setCurrentSlide(currentSlide - 1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [fileId, currentSlide, pageCount, setCurrentSlide])

  // AI 요약 요청
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

  // 노트 텍스트 디바운스 자동 저장 (주석은 persistRef로)
  useEffect(() => {
    if (!fileId) return
    const t = setTimeout(async () => {
      setSaving(true)
      try {
        if (persistRef.current) {
          await persistRef.current(noteText)
        }
      } finally {
        setSaving(false)
      }
    }, 500)
    return () => clearTimeout(t)
  }, [noteText, fileId, currentSlide])

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-4 py-2 bg-gray-950 border-b border-gray-700 shrink-0">
        <span className="font-semibold text-white text-sm">SlideNote</span>
        <div className="flex items-center gap-3">
          {fileId && (
            <span className="text-xs text-gray-400">
              {currentSlide} / {pageCount}
            </span>
          )}
          <UploadButton />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-48 bg-gray-900 border-r border-gray-700 overflow-y-auto p-2 shrink-0">
          <SlideList />
        </aside>

        {fileId ? (
          <SlideViewer persistRef={persistRef} stampRef={stampRef} />
        ) : (
          <main className="flex-1 flex items-center justify-center bg-gray-800">
            <div className="text-center text-gray-400">
              <p className="text-2xl mb-4">SlideNote</p>
              <p className="text-sm">상단 버튼으로 PPTX 또는 PDF를 업로드하세요</p>
            </div>
          </main>
        )}

        <aside className="w-80 bg-gray-900 border-l border-gray-700 p-4 flex flex-col shrink-0">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm font-semibold text-gray-300">노트 ({currentSlide}페이지)</h2>
            <span className="text-[10px] text-gray-500">{saving ? '저장 중…' : '자동 저장'}</span>
          </div>

          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            disabled={!fileId}
            className="flex-1 bg-gray-800 text-gray-200 text-sm p-2 rounded resize-none border border-gray-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            placeholder="발표 대본이나 메모를 입력하세요..."
          />

          {/* AI 요약 영역 */}
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

          {/* 오디오 녹음 패널 */}
          {fileId && <AudioPanel />}

          {fileId && (
            <div className="mt-2 flex flex-col gap-1">
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
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
