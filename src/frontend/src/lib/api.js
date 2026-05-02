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

export default api
