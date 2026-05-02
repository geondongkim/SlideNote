import { useState } from 'react'
import { uploadFile } from '../lib/api'
import { useAppStore } from '../store/useAppStore'

export default function UploadButton() {
  const setFile = useAppStore((s) => s.setFile)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const onChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const meta = await uploadFile(file)
      setFile(meta.fileId, meta.pageCount)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

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
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
    </div>
  )
}
