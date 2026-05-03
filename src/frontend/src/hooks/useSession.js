import { useCallback, useEffect, useState } from 'react'
import {
  collection,
  doc,
  setDoc,
  deleteDoc,
  onSnapshot,
  serverTimestamp,
  query,
  orderBy,
} from 'firebase/firestore'
import { db } from '../lib/firebase'

/**
 * Firestore 사용자별 파일 세션 관리
 * 컬렉션: sessions/{uid}/files/{fileId}
 *
 * @param {string|null} uid - Firebase Auth UID
 * @returns {{ sessionFiles, saveSession, removeSession }}
 */
export function useSession(uid) {
  const [sessionFiles, setSessionFiles] = useState([])

  // 실시간 파일 목록 구독
  useEffect(() => {
    if (!uid) {
      setSessionFiles([])
      return
    }
    const q = query(
      collection(db, 'sessions', uid, 'files'),
      orderBy('lastOpenedAt', 'desc')
    )
    const unsub = onSnapshot(q, (snap) => {
      setSessionFiles(snap.docs.map((d) => ({ id: d.id, ...d.data() })))
    })
    return unsub
  }, [uid])

  /**
   * 파일 세션 저장/업데이트
   * @param {{ fileId, filename, pageCount, ext, storageUrl? }} meta
   */
  const saveSession = useCallback(
    async (meta) => {
      if (!uid) return
      const docRef = doc(db, 'sessions', uid, 'files', meta.fileId)
      await setDoc(
        docRef,
        {
          ...meta,
          uid,
          lastOpenedAt: serverTimestamp(),
        },
        { merge: true }
      )
    },
    [uid]
  )

  /**
   * 파일 세션 삭제
   * @param {string} fileId
   */
  const removeSession = useCallback(
    async (fileId) => {
      if (!uid) return
      const docRef = doc(db, 'sessions', uid, 'files', fileId)
      await deleteDoc(docRef)
    },
    [uid]
  )

  return { sessionFiles, saveSession, removeSession }
}
