import { useEffect, useCallback } from 'react'
import { useAppStore } from '../store/useAppStore'

/**
 * 발표 모드 — 전체화면 슬라이드 뷰어
 * Props:
 *   onExit: () => void  — 발표 종료 콜백
 */
export default function PresentationMode({ onExit }) {
  const { fileId, currentSlide, pageCount, setCurrentSlide } = useAppStore()

  const goPrev = useCallback(() => {
    if (currentSlide > 1) setCurrentSlide(currentSlide - 1)
  }, [currentSlide, setCurrentSlide])

  const goNext = useCallback(() => {
    if (currentSlide < pageCount) setCurrentSlide(currentSlide + 1)
  }, [currentSlide, pageCount, setCurrentSlide])

  // 키보드 ←/→/ESC
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') goNext()
      else if (e.key === 'ArrowLeft') goPrev()
      else if (e.key === 'Escape') onExit()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [goNext, goPrev, onExit])

  // 전체화면 진입 요청
  useEffect(() => {
    const el = document.documentElement
    if (el.requestFullscreen) el.requestFullscreen().catch(() => {})
    return () => {
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {})
      }
    }
  }, [])

  if (!fileId) return null

  const slideUrl = `/uploads/${fileId}/slides/page_${String(currentSlide).padStart(2, '0')}.png`

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center">
      {/* 슬라이드 이미지 */}
      <div className="flex-1 w-full flex items-center justify-center overflow-hidden p-4">
        <img
          src={slideUrl}
          alt={`슬라이드 ${currentSlide}`}
          className="max-w-full max-h-full object-contain select-none"
          draggable={false}
        />
      </div>

      {/* 컨트롤 바 (하단, hover 시 표시) */}
      <div className="flex items-center gap-4 pb-4 opacity-30 hover:opacity-100 transition-opacity duration-300">
        <button
          onClick={goPrev}
          disabled={currentSlide <= 1}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-700 hover:bg-gray-500 text-white disabled:opacity-30 text-lg transition-colors"
          title="이전 슬라이드 (←)"
        >
          ‹
        </button>

        <span className="text-gray-300 text-sm min-w-[60px] text-center select-none">
          {currentSlide} / {pageCount}
        </span>

        <button
          onClick={goNext}
          disabled={currentSlide >= pageCount}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-700 hover:bg-gray-500 text-white disabled:opacity-30 text-lg transition-colors"
          title="다음 슬라이드 (→)"
        >
          ›
        </button>

        <button
          onClick={onExit}
          className="ml-4 px-3 py-1.5 rounded bg-red-700 hover:bg-red-600 text-white text-xs transition-colors"
          title="발표 종료 (ESC)"
        >
          ✕ 종료
        </button>
      </div>
    </div>
  )
}
