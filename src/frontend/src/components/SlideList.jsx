import { useEffect, useState } from 'react'
import { useAppStore } from '../store/useAppStore'
import { fetchSlides } from '../lib/api'

export default function SlideList() {
  const { fileId, pageCount, currentSlide, setCurrentSlide } = useAppStore()
  const [slides, setSlides] = useState([])

  useEffect(() => {
    if (!fileId) {
      setSlides([])
      return
    }
    fetchSlides(fileId).then((d) => setSlides(d.slides))
  }, [fileId, pageCount])

  if (!fileId) {
    return <p className="text-xs text-gray-400 text-center mt-4">슬라이드 목록</p>
  }

  return (
    <ul className="space-y-1">
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
  )
}
