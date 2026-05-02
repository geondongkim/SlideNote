import { useEffect, useState } from 'react'
import { useAppStore } from './store/useAppStore'
import { fetchNote, saveNote } from './lib/api'
import UploadButton from './components/UploadButton'
import SlideList from './components/SlideList'

export default function App() {
  const { fileId, currentSlide } = useAppStore()
  const [noteText, setNoteText] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!fileId) return
    fetchNote(fileId, currentSlide).then((n) => setNoteText(n.text || ''))
  }, [fileId, currentSlide])

  useEffect(() => {
    if (!fileId) return
    const t = setTimeout(async () => {
      setSaving(true)
      try {
        await saveNote(fileId, currentSlide, { text: noteText, annotations: {}, ai_summary: '' })
      } finally {
        setSaving(false)
      }
    }, 500)
    return () => clearTimeout(t)
  }, [noteText, fileId, currentSlide])

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-48 bg-gray-900 border-r border-gray-700 overflow-y-auto p-2">
        <SlideList />
      </aside>

      <main className="flex-1 flex items-center justify-center bg-gray-800 relative">
        {fileId ? (
          <img
            src={`/uploads/${fileId}/slides/page_${String(currentSlide).padStart(2, '0')}.png`}
            alt={`슬라이드 ${currentSlide}`}
            className="max-h-full max-w-full object-contain shadow-xl"
          />
        ) : (
          <div className="text-center text-gray-400">
            <p className="text-2xl mb-4">SlideNote</p>
            <p className="text-sm mb-6">PPTX 또는 PDF를 업로드하세요</p>
            <UploadButton />
          </div>
        )}
      </main>

      <aside className="w-80 bg-gray-900 border-l border-gray-700 p-4 flex flex-col">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-sm font-semibold text-gray-300">노트 (슬라이드 {currentSlide})</h2>
          <span className="text-[10px] text-gray-500">{saving ? '저장 중…' : '자동 저장'}</span>
        </div>
        <textarea
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          disabled={!fileId}
          className="flex-1 bg-gray-800 text-gray-200 text-sm p-2 rounded resize-none border border-gray-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          placeholder="발표 대본이나 메모를 입력하세요..."
        />
        <button
          disabled
          className="mt-2 bg-blue-600 disabled:bg-gray-600 text-white text-sm py-1 rounded"
        >
          AI 요약 생성 (Phase 2)
        </button>
      </aside>
    </div>
  )
}
