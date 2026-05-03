import { useEffect, useState } from 'react'
import { fetchFiles, deleteFile } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { fetchSlides } from '../lib/api'

/**
 * 최근 파일 목록 — 초기 화면에 표시
 * 파일 클릭 시 해당 파일을 불러옴
 */
export default function RecentFiles() {
  const { setFile } = useAppStore()
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)

  const loadFiles = async () => {
    setLoading(true)
    try {
      const data = await fetchFiles()
      setFiles(data)
    } catch {
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFiles()
  }, [])

  const handleOpen = async (fileId, pageCount) => {
    setFile(fileId, pageCount)
  }

  const handleDelete = async (e, fileId) => {
    e.stopPropagation()
    if (!confirm('이 파일을 삭제하시겠습니까?')) return
    setDeletingId(fileId)
    try {
      await deleteFile(fileId)
      setFiles((prev) => prev.filter((f) => f.fileId !== fileId))
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        파일 목록 로딩 중…
      </div>
    )
  }

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
        <p className="text-2xl">📂</p>
        <p className="text-sm">최근 열었던 파일이 없습니다</p>
        <p className="text-xs">상단 버튼으로 PPTX 또는 PDF를 업로드하세요</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full p-6 overflow-y-auto">
      <h2 className="text-gray-300 text-sm font-semibold mb-4">최근 파일</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {files.map((f) => (
          <div
            key={f.fileId}
            onClick={() => handleOpen(f.fileId, f.pageCount)}
            className="group relative bg-gray-900 border border-gray-700 rounded-lg overflow-hidden cursor-pointer hover:border-blue-500 transition-colors"
          >
            {/* 썸네일 */}
            <div className="aspect-video bg-gray-800 overflow-hidden">
              <img
                src={f.thumbnail}
                alt={f.filename}
                className="w-full h-full object-cover"
                onError={(e) => { e.target.style.display = 'none' }}
              />
            </div>
            {/* 정보 */}
            <div className="p-2">
              <p className="text-gray-200 text-xs font-medium truncate" title={f.filename}>
                {f.filename}
              </p>
              <p className="text-gray-500 text-[10px] mt-0.5">
                {f.pageCount}페이지 &middot; {_formatDate(f.uploadedAt)}
              </p>
            </div>
            {/* 삭제 버튼 */}
            <button
              onClick={(e) => handleDelete(e, f.fileId)}
              disabled={deletingId === f.fileId}
              className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 bg-red-600 hover:bg-red-700 text-white rounded px-1.5 py-0.5 text-[10px] transition-opacity"
            >
              {deletingId === f.fileId ? '…' : '삭제'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function _formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
