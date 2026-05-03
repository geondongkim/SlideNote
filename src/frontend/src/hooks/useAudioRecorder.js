/**
 * MediaRecorder 기반 슬라이드별 오디오 녹음 훅
 *
 * 설계:
 * - 녹음 중 stamp(annotationId) 호출 → 현재 elapsed 시간을 timestamps Map에 기록
 * - 중지 시 WebM Blob → /api/audio/{fileId}/{page} 업로드
 * - 재생 시 annotationId로 currentTime 이동
 */
import { useRef, useState, useCallback } from 'react'
import { uploadAudio, fetchAudio } from '../lib/api'

export function useAudioRecorder(fileId, page) {
  const mediaRef = useRef(null)       // MediaRecorder 인스턴스
  const chunksRef = useRef([])        // 녹음 청크
  const startedAtRef = useRef(null)   // 녹음 시작 Date.now()
  const audioBlobRef = useRef(null)   // 최신 WebM Blob
  const audioElRef = useRef(null)     // <audio> 엘리먼트 참조 (재생용)
  const audioUrlRef = useRef(null)    // createObjectURL 캐시

  const [recording, setRecording] = useState(false)
  const [hasAudio, setHasAudio] = useState(false)
  const [timestamps, setTimestamps] = useState({}) // { annotationId → seconds }

  // ── 녹음 시작 ──
  const startRecording = useCallback(async () => {
    if (recording) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        audioBlobRef.current = blob
        // URL 갱신
        if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
        audioUrlRef.current = URL.createObjectURL(blob)
        setHasAudio(true)
        // 서버 업로드 (비동기, 실패해도 로컬 재생은 유지)
        if (fileId) {
          uploadAudio(fileId, page, blob, timestamps).catch(console.warn)
        }
      }
      mediaRef.current = recorder
      startedAtRef.current = Date.now()
      recorder.start(500) // 500ms 청크
      setRecording(true)
    } catch (e) {
      console.error('마이크 접근 실패:', e)
    }
  }, [recording, fileId, page, timestamps])

  // ── 녹음 중지 ──
  const stopRecording = useCallback(() => {
    if (!recording || !mediaRef.current) return
    mediaRef.current.stop()
    setRecording(false)
  }, [recording])

  // ── 현재 시점 스탬프 기록 ──
  const stamp = useCallback((annotationId) => {
    if (!recording || !startedAtRef.current) return
    const elapsed = (Date.now() - startedAtRef.current) / 1000
    setTimestamps((prev) => ({ ...prev, [annotationId]: elapsed }))
    return elapsed
  }, [recording])

  // ── 특정 주석 시점으로 점프 재생 ──
  const playFrom = useCallback((annotationId) => {
    const t = timestamps[annotationId]
    if (t == null || !audioUrlRef.current) return
    if (!audioElRef.current) {
      audioElRef.current = new Audio(audioUrlRef.current)
    } else {
      audioElRef.current.src = audioUrlRef.current
    }
    audioElRef.current.currentTime = t
    audioElRef.current.play()
  }, [timestamps])

  // ── 서버에서 오디오 + timestamps 로드 ──
  const loadAudio = useCallback(async () => {
    if (!fileId) return
    try {
      const { blob, timestamps: ts } = await fetchAudio(fileId, page)
      if (blob) {
        if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
        audioUrlRef.current = URL.createObjectURL(blob)
        setHasAudio(true)
      }
      if (ts) setTimestamps(ts)
    } catch {
      // 오디오 없는 슬라이드는 정상
    }
  }, [fileId, page])

  // ── 전체 오디오 재생/정지 토글 ──
  const togglePlay = useCallback(() => {
    if (!audioUrlRef.current) return
    if (!audioElRef.current) {
      audioElRef.current = new Audio(audioUrlRef.current)
    } else {
      audioElRef.current.src = audioUrlRef.current
    }
    if (audioElRef.current.paused) {
      audioElRef.current.play()
    } else {
      audioElRef.current.pause()
    }
  }, [])

  return {
    recording,
    hasAudio,
    timestamps,
    startRecording,
    stopRecording,
    stamp,
    playFrom,
    loadAudio,
    togglePlay,
    audioUrlRef,
  }
}
