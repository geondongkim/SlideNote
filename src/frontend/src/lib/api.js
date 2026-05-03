import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const uploadFile = async (file) => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/files/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const fetchSlides = async (fileId) => {
  const { data } = await api.get(`/files/${fileId}/slides`)
  return data
}

export const fetchNote = async (fileId, page) => {
  const { data } = await api.get(`/notes/${fileId}/${page}`)
  return data
}

export const saveNote = async (fileId, page, payload) => {
  const { data } = await api.put(`/notes/${fileId}/${page}`, payload)
  return data
}

export const summarizeSlide = async (fileId, page) => {
  const { data } = await api.post(`/ai/${fileId}/summarize`, { page })
  return data
}

export const uploadAudio = async (fileId, page, blob, timestamps) => {
  const form = new FormData()
  form.append('audio', blob, `slide_${String(page).padStart(2, '0')}.webm`)
  await api.post(`/audio/${fileId}/${page}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  if (timestamps && Object.keys(timestamps).length > 0) {
    await api.put(`/audio/${fileId}/${page}/timestamps`, { audio_timestamps: timestamps })
  }
}

export const fetchAudio = async (fileId, page) => {
  // 노트에서 timestamps 로드
  const note = await fetchNote(fileId, page)
  if (!note.audio_url) return { blob: null, timestamps: {} }
  // 오디오 바이너리 fetch
  const resp = await fetch(note.audio_url)
  if (!resp.ok) return { blob: null, timestamps: note.audio_timestamps || {} }
  const blob = await resp.blob()
  return { blob, timestamps: note.audio_timestamps || {} }
}

export const downloadHandout = (fileId, layout = '2up') => {
  const url = `/api/export/${fileId}/handout?layout=${layout}`
  const a = document.createElement('a')
  a.href = url
  a.download = `slidenote_handout_${layout}.pdf`
  a.click()
}

export const insertWhiteboardPage = async (fileId) => {
  const { data } = await api.post(`/files/${fileId}/whiteboard`)
  return data  // { page, url, pageCount }
}

export const fetchFiles = async () => {
  const { data } = await api.get('/files')
  return data  // [{ fileId, filename, pageCount, uploadedAt, thumbnail }, ...]
}

export const deleteFile = async (fileId) => {
  await api.delete(`/files/${fileId}`)
}

export const downloadNotesMarkdown = (fileId, filename = 'notes') => {
  const url = `/api/export/${fileId}/notes.md`
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}_notes.md`
  a.click()
}

/**
 * 업로드 후 SSE 진행률 구독
 * @param {string} fileId
 * @param {(state: {status:string, page:number, total:number}) => void} onProgress
 * @returns {() => void} cleanup 함수
 */
export const subscribeUploadProgress = (fileId, onProgress) => {
  const es = new EventSource(`/api/files/upload/${fileId}/progress`)
  es.onmessage = (e) => {
    try {
      const state = JSON.parse(e.data)
      onProgress(state)
      if (state.status === 'done' || state.status === 'error' || state.status === 'timeout') {
        es.close()
      }
    } catch {/* ignore */}
  }
  es.onerror = () => es.close()
  return () => es.close()
}

export default api
