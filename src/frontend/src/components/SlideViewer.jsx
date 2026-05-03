/**
 * 중앙 슬라이드 뷰어 + Fabric.js 주석 Canvas 오버레이
 * - 이미지 위에 canvas를 절대 위치로 겹쳐 정확한 좌표 일치 보장
 * - 이미지 로드/리사이즈 시 canvas 크기 자동 동기화
 * - 화이트보드 페이지: 흰 PNG 위에 주석 도구 그대로 사용
 */
import { useRef, useCallback, useEffect } from 'react'
import { useAppStore } from '../store/useAppStore'
import { useAnnotation } from '../hooks/useAnnotation'
import Toolbar from './Toolbar'

export default function SlideViewer({ persistRef, stampRef, whiteboardPages = new Set() }) {
  const { fileId, currentSlide } = useAppStore()
  const imgRef = useRef(null)
  const canvasRef = useRef(null)

  const annotation = useAnnotation(canvasRef, fileId, currentSlide, stampRef)

  // App이 노트 저장 시 persistAnnotations 호출 가능하도록 ref 연결
  useEffect(() => {
    if (persistRef) persistRef.current = annotation.persistAnnotations
  }, [annotation.persistAnnotations, persistRef])

  const onImageLoad = useCallback(() => {
    annotation.resizeToImage(imgRef.current)
  }, [annotation])

  if (!fileId) return null

  const slideUrl = `/uploads/${fileId}/slides/page_${String(currentSlide).padStart(2, '0')}.png`
  const isWhiteboard = whiteboardPages.has(currentSlide)

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-800">
      <Toolbar annotation={annotation} />

      {/* 화이트보드 뱃지 */}
      {isWhiteboard && (
        <div className="px-3 py-1 bg-yellow-900/40 border-b border-yellow-700/50 text-yellow-300 text-xs text-center select-none">
          ✏ 화이트보드 페이지 — 자유롭게 드로잉하세요
        </div>
      )}

      {/* 뷰어 영역: 이미지 + canvas 겹치기 */}
      <div className="flex-1 flex items-center justify-center overflow-auto p-4">
        <div className="relative inline-block shadow-2xl">
          <img
            ref={imgRef}
            src={slideUrl}
            alt={`슬라이드 ${currentSlide}`}
            onLoad={onImageLoad}
            className="block max-h-[calc(100vh-9rem)] max-w-full"
            draggable={false}
          />
          {/* Canvas: 이미지 위 정확히 겹침 */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0"
            style={{ touchAction: 'none' }}
          />
        </div>
      </div>
    </div>
  )
}
