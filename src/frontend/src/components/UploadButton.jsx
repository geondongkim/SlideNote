import { useState } from 'react'
import { uploadFile, subscribeUploadProgress } from '../lib/api'
import { useAppStore } from '../store/useAppStore'

/**
 * @param {{ onSuccess?: (file: File, meta: object) => void }} props
 */
export default function UploadButton({ onSuccess }) {
  const setFile = useAppStore((s) => s.setFile)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(null)  // null | { page, total, status }

  const onChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    setProgress({ page: 0, total: 0, status: 'uploading' })
    try {
      const meta = await uploadFile(file)
      setProgress({ page: meta.pageCount, total: meta.pageCount, status: 'done' })
      // SSE로 변환 완료 확인 (이미 완료됐으면 즉시 done 수신)
      subscribeUploadProgress(meta.fileId, (state) => {
        setProgress(state)
      })
      setFile(meta.fileId, meta.pageCount)
      onSuccess?.(file, meta)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setProgress(null)
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  const pct = progress && progress.total > 0
    ? Math.round((progress.page / progress.total) * 100)
    : null

  return (
    <div className="text-center">
      <label className="inline-block cursor-pointer bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded">
        {loading ? '변환 중…' : 'PPTX / PDF 업로드'}
        <input
          type="file"
          accept=".pdf,.pptx"
          className="hidden"
          onChange={onChange}
          disabled={loading}
        />
      </label>
      {/* 진행률 바 */}
      {progress && progress.status !== 'done' && (
        <div className="mt-1.5 w-40">
          <div className="h-1 bg-gray-700 rounded overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: pct !== null ? `${pct}%` : '30%', animation: pct === null ? 'pulse 1s infinite' : 'none' }}
            />
          </div>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {pct !== null ? `${progress.page} / ${progress.total} 페이지` : '변환 중…'}
          </p>
        </div>
      )}
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </div>
  )
}
