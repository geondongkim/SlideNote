import { useCallback, useEffect, useRef } from 'react'
import {
  doc,
  getDoc,
  setDoc,
  onSnapshot,
  serverTimestamp,
} from 'firebase/firestore'
import { db } from '../lib/firebase'

/**
 * Firestore 노트/주석 실시간 동기화 훅
 *
 * @param {string|null} uid    - Firebase Auth UID (null이면 비활성)
 * @param {string|null} fileId - 업로드된 파일 ID
 * @param {number}      page   - 현재 슬라이드 번호
 * @param {(text:string, annotations:object) => void} onRemoteUpdate
 *   - 원격에서 변경됐을 때 호출되는 콜백
 * @returns {{ syncNote: (text:string, annotations:object) => Promise<void> }}
 */
export function useFirestore(uid, fileId, page, onRemoteUpdate) {
  // 원격 업데이트 콜백을 ref로 안정화 (리렌더링에 무관)
  const cbRef = useRef(onRemoteUpdate)
  useEffect(() => { cbRef.current = onRemoteUpdate }, [onRemoteUpdate])

  // Firestore 문서 경로: notes/{uid}_{fileId}_{page}
  const docId = uid && fileId ? `${uid}_${fileId}_${page}` : null

  // 실시간 리스너
  useEffect(() => {
    if (!docId) return
    const ref = doc(db, 'notes', docId)
    const unsub = onSnapshot(ref, (snap) => {
      if (!snap.exists()) return
      const data = snap.data()
      cbRef.current?.(data.text ?? '', data.annotations ?? {})
    })
    return unsub
  }, [docId])

  // 노트/주석 Firestore에 저장
  const syncNote = useCallback(
    async (text, annotations) => {
      if (!docId) return
      const ref = doc(db, 'notes', docId)
      await setDoc(
        ref,
        {
          uid,
          fileId,
          page,
          text,
          annotations,
          updatedAt: serverTimestamp(),
        },
        { merge: true }
      )
    },
    [docId, uid, fileId, page]
  )

  return { syncNote }
}
