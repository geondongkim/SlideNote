/**
 * Fabric.js 기반 주석 훅
 * Undo/Redo: pympress scribble_list 패턴 (스냅샷 스택, 최대 50단계)
 * 주석 스키마: id(uuid), _pageRatio([w,h]), _timestamp(null) — 변경 금지
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { fabric } from 'fabric'
import { v4 as uuidv4 } from 'uuid'
import { saveNote, fetchNote } from '../lib/api'

const BRUSH_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7', '#ffffff', '#000000']
const MAX_HISTORY = 50

export function useAnnotation(canvasRef, fileId, page, stampRef) {
  const fabricRef = useRef(null)
  const historyRef = useRef([])   // pympress: scribble_list
  const redoRef = useRef([])      // pympress: scribble_redo_list
  const pageRatioRef = useRef([1, 1])

  const [tool, setTool] = useState('select')
  const [color, setColor] = useState(BRUSH_COLORS[0])
  const [brushWidth, setBrushWidth] = useState(3)
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)

  // ── 캔버스 초기화 ──
  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = new fabric.Canvas(canvasRef.current, {
      isDrawingMode: false,
      selection: true,
      renderOnAddRemove: true,
    })
    fabricRef.current = canvas

    // 객체 추가 시 id/_pageRatio 자동 부여
    canvas.on('object:added', (e) => {
      const obj = e.target
      if (!obj.id) obj.id = uuidv4()
      if (!obj._pageRatio) obj._pageRatio = [...pageRatioRef.current]
      if (!obj._timestamp) obj._timestamp = null
      // 녹음 중이면 현재 시점 기록
      if (stampRef?.current && obj.id) {
        const elapsed = stampRef.current(obj.id)
        if (elapsed != null) obj._timestamp = elapsed
      }
      _saveSnapshot()
    })

    canvas.on('object:modified', _saveSnapshot)

    return () => canvas.dispose()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── 파일/페이지 변경 시 주석 로드 ──
  useEffect(() => {
    if (!fabricRef.current || !fileId) return
    fabricRef.current.clear()
    historyRef.current = []
    redoRef.current = []
    _syncHistory()

    fetchNote(fileId, page).then((note) => {
      const json = note.annotations
      if (json?.objects?.length) {
        fabricRef.current.loadFromJSON(json, () => fabricRef.current.renderAll())
        _saveSnapshot()
      } else {
        _saveSnapshot()
      }
    })
  }, [fileId, page])

  // ── 도구 변경 반영 ──
  useEffect(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    canvas.isDrawingMode = tool === 'pen' || tool === 'highlight'
    canvas.selection = tool === 'select'
    if (canvas.isDrawingMode) {
      canvas.freeDrawingBrush.color =
        tool === 'highlight' ? _toRgba(color, 0.4) : color
      canvas.freeDrawingBrush.width = tool === 'highlight' ? 20 : brushWidth
    }
  }, [tool, color, brushWidth])

  // ── Undo/Redo ──
  const _saveSnapshot = useCallback(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    const snap = canvas.toJSON(['id', '_pageRatio', '_timestamp'])
    historyRef.current.push(snap)
    redoRef.current = []
    if (historyRef.current.length > MAX_HISTORY) historyRef.current.shift()
    _syncHistory()
  }, [])

  const undo = useCallback(() => {
    if (historyRef.current.length < 2) return
    const last = historyRef.current.pop()
    redoRef.current.push(last)
    const prev = historyRef.current.at(-1)
    fabricRef.current.loadFromJSON(prev, () => fabricRef.current.renderAll())
    _syncHistory()
  }, [])

  const redo = useCallback(() => {
    if (!redoRef.current.length) return
    const next = redoRef.current.pop()
    historyRef.current.push(next)
    fabricRef.current.loadFromJSON(next, () => fabricRef.current.renderAll())
    _syncHistory()
  }, [])

  const _syncHistory = () => {
    setCanUndo(historyRef.current.length > 1)
    setCanRedo(redoRef.current.length > 0)
  }

  // ── 텍스트 추가 ──
  const addText = useCallback(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    const text = new fabric.IText('텍스트 입력', {
      left: 100, top: 100,
      fontSize: 18, fill: color,
      id: uuidv4(), _pageRatio: [...pageRatioRef.current], _timestamp: null,
    })
    canvas.add(text)
    canvas.setActiveObject(text)
    text.enterEditing()
  }, [color])

  // ── 화살표 추가 ──
  const addArrow = useCallback(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    const line = new fabric.Line([80, 80, 200, 200], {
      stroke: color, strokeWidth: brushWidth, selectable: true,
      id: uuidv4(), _pageRatio: [...pageRatioRef.current], _timestamp: null,
    })
    canvas.add(line)
    canvas.setActiveObject(line)
  }, [color, brushWidth])

  // ── 선택 삭제 ──
  const deleteSelected = useCallback(() => {
    const canvas = fabricRef.current
    if (!canvas) return
    const active = canvas.getActiveObjects()
    if (!active.length) return
    active.forEach((obj) => canvas.remove(obj))
    canvas.discardActiveObject()
    canvas.renderAll()
    _saveSnapshot()
  }, [_saveSnapshot])

  // ── 전체 지우기 ──
  const clearAll = useCallback(() => {
    fabricRef.current?.clear()
    _saveSnapshot()
  }, [_saveSnapshot])

  // ── 저장 (PUT /api/notes) ──
  const persistAnnotations = useCallback(async (noteText) => {
    if (!fileId || !fabricRef.current) return
    const json = fabricRef.current.toJSON(['id', '_pageRatio', '_timestamp'])
    await saveNote(fileId, page, { text: noteText || '', annotations: json, ai_summary: '' })
  }, [fileId, page])

  // ── 캔버스 크기를 이미지에 맞춰 조정 ──
  const resizeToImage = useCallback((imgEl) => {
    const canvas = fabricRef.current
    if (!canvas || !imgEl) return
    canvas.setWidth(imgEl.clientWidth)
    canvas.setHeight(imgEl.clientHeight)
    pageRatioRef.current = [imgEl.naturalWidth, imgEl.naturalHeight]
    canvas.renderAll()
  }, [])

  return {
    BRUSH_COLORS,
    tool, setTool,
    color, setColor,
    brushWidth, setBrushWidth,
    canUndo, canRedo,
    undo, redo,
    addText, addArrow,
    deleteSelected, clearAll,
    persistAnnotations, resizeToImage,
    fabricRef,
  }
}

function _toRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
