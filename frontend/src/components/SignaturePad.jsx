import { useRef, useEffect, useCallback } from 'react'

export default function SignaturePad({ width = 560, height = 200, onSignatureChange }) {
  const canvasRef = useRef(null)
  const isDrawing = useRef(false)
  const lastPoint = useRef(null)
  const hasDrawn = useRef(false)

  const getPoint = useCallback((e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    if (e.touches) {
      return {
        x: (e.touches[0].clientX - rect.left) * scaleX,
        y: (e.touches[0].clientY - rect.top) * scaleY,
      }
    }
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    }
  }, [])

  const startDraw = useCallback((e) => {
    e.preventDefault()
    isDrawing.current = true
    lastPoint.current = getPoint(e)
  }, [getPoint])

  const draw = useCallback((e) => {
    if (!isDrawing.current) return
    e.preventDefault()
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const point = getPoint(e)
    const prev = lastPoint.current

    ctx.beginPath()
    ctx.moveTo(prev.x, prev.y)
    ctx.lineTo(point.x, point.y)
    ctx.strokeStyle = '#1a1a1a'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.stroke()

    lastPoint.current = point
    hasDrawn.current = true
  }, [getPoint])

  const endDraw = useCallback(() => {
    if (!isDrawing.current) return
    isDrawing.current = false
    lastPoint.current = null
    if (hasDrawn.current && onSignatureChange) {
      const canvas = canvasRef.current
      onSignatureChange(canvas.toDataURL('image/png'))
    }
  }, [onSignatureChange])

  const clear = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    hasDrawn.current = false
    if (onSignatureChange) onSignatureChange(null)
  }, [onSignatureChange])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const handleTouchStart = (e) => startDraw(e)
    const handleTouchMove = (e) => draw(e)
    const handleTouchEnd = () => endDraw()

    canvas.addEventListener('touchstart', handleTouchStart, { passive: false })
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false })
    canvas.addEventListener('touchend', handleTouchEnd)

    return () => {
      canvas.removeEventListener('touchstart', handleTouchStart)
      canvas.removeEventListener('touchmove', handleTouchMove)
      canvas.removeEventListener('touchend', handleTouchEnd)
    }
  }, [startDraw, draw, endDraw])

  return (
    <div style={{ maxWidth: width, width: '100%' }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onMouseDown={startDraw}
        onMouseMove={draw}
        onMouseUp={endDraw}
        onMouseLeave={endDraw}
        style={{
          width: '100%',
          height: 'auto',
          border: '1px solid #d1d5db',
          borderRadius: '8px',
          background: '#ffffff',
          cursor: 'crosshair',
          touchAction: 'none',
          display: 'block',
        }}
      />
      <button
        type="button"
        onClick={clear}
        style={{
          marginTop: '8px',
          padding: '6px 16px',
          fontSize: '13px',
          color: '#6b7280',
          background: '#f3f4f6',
          border: '1px solid #d1d5db',
          borderRadius: '6px',
          cursor: 'pointer',
        }}
      >
        Clear Signature
      </button>
    </div>
  )
}
