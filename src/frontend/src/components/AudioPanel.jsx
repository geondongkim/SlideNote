/**
 * 오디오 녹음 패널
 * - 녹음 시작/중지
 * - 전체 재생
 * - 주석 시점 스탬프 표시 (주석 ID → 초)
 */
import { useEffect } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useAudioRecorder } from '../hooks/useAudioRecorder'

// 초 → mm:ss 포맷
function fmt(sec) {
  const m = Math.floor(sec / 60).toString().padStart(2, '0')
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export default function AudioPanel({ stampTrigger }) {
  const { fileId, currentSlide } = useAppStore()
  const {
    recording,
    hasAudio,
    timestamps,
    startRecording,
    stopRecording,
    loadAudio,
    togglePlay,
  } = useAudioRecorder(fileId, currentSlide)

  // 슬라이드 변경 시 오디오 로드
  useEffect(() => {
    loadAudio()
  }, [fileId, currentSlide, loadAudio])

  // 외부(Toolbar)에서 stamp 트리거가 오면 호출
  // stampTrigger: { annotationId, stamp } — 부모가 useAudioRecorder 직접 참조하는 방식 사용 권장
  // 여기선 UI 상태만 표시

  const stampEntries = Object.entries(timestamps)

  return (
    <div className="mt-3 border border-gray-600 rounded p-2">
      <p className="text-[10px] text-orange-400 font-medium mb-2">오디오 녹음</p>

      {/* 녹음 컨트롤 */}
      <div className="flex gap-2 mb-2">
        {!recording ? (
          <button
            onClick={startRecording}
            disabled={!fileId}
            className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white text-xs py-1 rounded transition-colors"
          >
            ● 녹음 시작
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="flex-1 bg-red-800 hover:bg-red-900 text-white text-xs py-1 rounded animate-pulse"
          >
            ■ 녹음 중지
          </button>
        )}

        {hasAudio && (
          <button
            onClick={togglePlay}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs py-1 rounded"
          >
            ▶ 재생
          </button>
        )}
      </div>

      {/* 녹음 중 상태 표시 */}
      {recording && (
        <p className="text-[9px] text-red-400 mb-2 animate-pulse">
          ● 녹음 중… 주석 도구로 필기하면 시점이 자동 기록됩니다
        </p>
      )}

      {/* 타임스탬프 목록 */}
      {stampEntries.length > 0 && (
        <div className="max-h-24 overflow-y-auto">
          <p className="text-[9px] text-gray-500 mb-1">기록된 시점</p>
          {stampEntries.map(([id, sec]) => (
            <div key={id} className="flex justify-between text-[9px] text-gray-400 py-0.5">
              <span className="truncate w-32 font-mono">{id.slice(0, 8)}…</span>
              <span className="text-blue-400">{fmt(sec)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
