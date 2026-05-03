import { useEffect, useState } from 'react'
import { useAppStore } from '../store/useAppStore'
import { fetchSlides, insertWhiteboardPage } from '../lib/api'

export default function SlideList({ onWhiteboardInserted }) {
  const { fileId, pageCount, currentSlide, setCurrentSlide, setPageCount } = useAppStore()
  const [slides, setSlides] = useState([])
  const [inserting, setInserting] = useState(false)

  useEffect(() => {
    if (!fileId) {
      setSlides([])
      return
    }
    fetchSlides(fileId).then((d) => setSlides(d.slides))
  }, [fileId, pageCount])

  const handleInsertWhiteboard = async () => {
    if (!fileId || inserting) return
    setInserting(true)
    try {
      const result = await insertWhiteboardPage(fileId)
      setPageCount(result.pageCount)
      setSlides((prev) => [...prev, { page: result.page, url: result.url }])
      setCurrentSlide(result.page)
      onWhiteboardInserted?.(result.page)
    } finally {
      setInserting(false)
    }
  }

  if (!fileId) {
    return <p className="text-xs text-gray-400 text-center mt-4">슬라이드 목록</p>
  }

  return (
    <div className="flex flex-col h-full">
      <ul className="flex-1 space-y-1 overflow-y-auto">
        {slides.map((s) => (
          <li key={s.page}>
            <button
              onClick={() => setCurrentSlide(s.page)}
              className={`w-full text-left rounded overflow-hidden border ${
                s.page === currentSlide ? 'border-blue-500' : 'border-transparent'
              }`}
            >
              <img src={s.url} alt={`슬라이드 ${s.page}`} className="w-full" />
              <span className="block text-[10px] text-gray-400 px-1 py-0.5">{s.page}</span>
            </button>
          </li>
        ))}
      </ul>

      <button
        onClick={handleInsertWhiteboard}
        disabled={inserting}
        className="mt-2 w-full text-xs py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50 border border-dashed border-gray-500"
      >
        {inserting ? '추가 중…' : '+ 빈 페이지 삽입'}
      </button>
    </div>
  )
}
