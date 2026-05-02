/**
 * 주석 도구 모음 (슬라이드 뷰어 상단)
 * 도구: select | pen | highlight | text | arrow
 */
const TOOLS = [
  { id: 'select',    label: '선택',   icon: '↖' },
  { id: 'pen',       label: '펜',     icon: '✏️' },
  { id: 'highlight', label: '형광펜', icon: '🖌' },
  { id: 'text',      label: '텍스트', icon: 'T' },
  { id: 'arrow',     label: '화살표', icon: '→' },
]

export default function Toolbar({ annotation }) {
  const {
    BRUSH_COLORS,
    tool, setTool,
    color, setColor,
    brushWidth, setBrushWidth,
    canUndo, canRedo,
    undo, redo,
    addText, addArrow,
    deleteSelected, clearAll,
  } = annotation

  const onToolClick = (id) => {
    if (id === 'text') { setTool('select'); addText(); return }
    if (id === 'arrow') { setTool('select'); addArrow(); return }
    setTool(id)
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border-b border-gray-700 flex-wrap">
      {/* 도구 선택 */}
      {TOOLS.map((t) => (
        <button
          key={t.id}
          title={t.label}
          onClick={() => onToolClick(t.id)}
          className={`px-2.5 py-1 rounded text-sm font-medium transition-colors ${
            tool === t.id
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          {t.icon}
        </button>
      ))}

      <div className="w-px h-5 bg-gray-600 mx-1" />

      {/* 색상 팔레트 */}
      {BRUSH_COLORS.map((c) => (
        <button
          key={c}
          title={c}
          onClick={() => setColor(c)}
          style={{ backgroundColor: c }}
          className={`w-5 h-5 rounded-full border-2 ${
            color === c ? 'border-white scale-110' : 'border-transparent'
          } transition-transform`}
        />
      ))}

      <div className="w-px h-5 bg-gray-600 mx-1" />

      {/* 굵기 */}
      <input
        type="range"
        min={1}
        max={12}
        value={brushWidth}
        onChange={(e) => setBrushWidth(Number(e.target.value))}
        className="w-20 accent-blue-500"
        title={`굵기 ${brushWidth}`}
      />

      <div className="w-px h-5 bg-gray-600 mx-1" />

      {/* Undo / Redo */}
      <button
        onClick={undo}
        disabled={!canUndo}
        title="실행 취소 (Ctrl+Z)"
        className="px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-30 text-sm"
      >
        ↩
      </button>
      <button
        onClick={redo}
        disabled={!canRedo}
        title="다시 실행 (Ctrl+Y)"
        className="px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-30 text-sm"
      >
        ↪
      </button>

      <div className="flex-1" />

      {/* 삭제 버튼 */}
      <button
        onClick={deleteSelected}
        title="선택 항목 삭제"
        className="px-2 py-1 rounded bg-gray-700 text-red-400 hover:bg-red-800 text-sm"
      >
        선택 삭제
      </button>
      <button
        onClick={clearAll}
        title="전체 주석 지우기"
        className="px-2 py-1 rounded bg-gray-700 text-red-400 hover:bg-red-800 text-sm"
      >
        전체 지우기
      </button>
    </div>
  )
}
