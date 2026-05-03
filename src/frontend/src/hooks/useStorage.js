import { useCallback } from 'react'
import { ref, uploadBytes, getDownloadURL, deleteObject } from 'firebase/storage'
import { storage } from '../lib/firebase'

/**
 * Firebase Storage 파일 업로드/삭제 훅
 *
 * @param {string|null} uid - Firebase Auth UID
 * @returns {{ uploadToStorage, deleteFromStorage }}
 */
export function useStorage(uid) {
  /**
   * 파일을 Storage에 업로드 후 다운로드 URL 반환
   * 경로: users/{uid}/files/{fileId}/original{ext}
   */
  const uploadToStorage = useCallback(
    async (file, fileId) => {
      if (!uid) return null
      const ext = file.name.split('.').pop()
      const path = `users/${uid}/files/${fileId}/original.${ext}`
      const storageRef = ref(storage, path)
      await uploadBytes(storageRef, file)
      const url = await getDownloadURL(storageRef)
      return url
    },
    [uid]
  )

  /**
   * Storage에서 파일 삭제
   * 경로: users/{uid}/files/{fileId}/original{ext}
   */
  const deleteFromStorage = useCallback(
    async (fileId, ext) => {
      if (!uid) return
      const path = `users/${uid}/files/${fileId}/original.${ext}`
      const storageRef = ref(storage, path)
      await deleteObject(storageRef).catch(() => {})
    },
    [uid]
  )

  return { uploadToStorage, deleteFromStorage }
}
