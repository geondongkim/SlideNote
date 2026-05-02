import { useState } from 'react'

// TODO: 컴포넌트 분리 예정
// import SlideList from './components/SlideList'
// import SlideViewer from './components/SlideViewer'
// import NoteEditor from './components/NoteEditor'

export default function App() {
  const [fileId, setFileId] = useState(null)
  const [currentSlide, setCurrentSlide] = useState(1)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 좌측: 슬라이드 목록 */}
      <aside className="w-48 bg-gray-900 border-r border-gray-700 overflow-y-auto p-2">
        <p className="text-xs text-gray-400 text-center mt-4">슬라이드 목록</p>
      </aside>

      {/* 중앙: 슬라이드 뷰어 + 주석 Canvas */}
      <main className="flex-1 flex items-center justify-center bg-gray-800">
        {fileId ? (
          <img
            src={`/uploads/${fileId}/slides/page_${String(currentSlide).padStart(2, '0')}.png`}
            alt={`슬라이드 ${currentSlide}`}
            className="max-h-full max-w-full object-contain shadow-xl"
          />
        ) : (
          <div className="text-center text-gray-400">
            <p className="text-lg mb-2">SlideNote</p>
            <p className="text-sm">PPTX 또는 PDF를 업로드하세요</p>
          </div>
        )}
      </main>

      {/* 우측: 노트 에디터 */}
      <aside className="w-80 bg-gray-900 border-l border-gray-700 p-4 flex flex-col">
        <h2 className="text-sm font-semibold text-gray-300 mb-2">노트</h2>
        <textarea
          className="flex-1 bg-gray-800 text-gray-200 text-sm p-2 rounded resize-none border border-gray-600 focus:outline-none focus:border-blue-500"
          placeholder="발표 대본이나 메모를 입력하세요..."
        />
        <button className="mt-2 bg-blue-600 hover:bg-blue-700 text-white text-sm py-1 rounded">
          AI 요약 생성
        </button>
      </aside>
    </div>
  )
}
