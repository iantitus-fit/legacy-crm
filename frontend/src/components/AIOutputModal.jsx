import { useEffect, useState } from 'react'
import { Copy, Loader2, Sparkles, X } from 'lucide-react'
import { dismissAIAction, generateAI, useAIAction } from '../api/ai'
import { useToast } from '../context/ToastContext'

/**
 * Modal that triggers an AI generation on open and displays the output.
 * Supports an optional Apply action (e.g. "Apply to Estimate") configured
 * by the parent.
 */
export default function AIOutputModal({
  isOpen,
  onClose,
  title = 'AI Output',
  eventType,
  contactId,
  estimateId,
  extra,
  onApply, // optional async (action) => void
  applyLabel = 'Apply',
}) {
  const { addToast } = useToast()
  const [loading, setLoading] = useState(false)
  const [action, setAction] = useState(null)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setAction(null)
    setError('')
    setLoading(true)
    generateAI({ eventType, contactId, estimateId, extra })
      .then(setAction)
      .catch((err) => {
        const detail = err?.response?.data?.detail
        if (err?.response?.status === 503) {
          setError(detail || 'AI is disabled.')
        } else {
          setError(detail || 'AI generation failed.')
        }
      })
      .finally(() => setLoading(false))
  }, [isOpen, eventType, contactId, estimateId])

  const handleCopy = async () => {
    if (!action?.output) return
    try {
      await navigator.clipboard.writeText(action.output)
      addToast('Copied to clipboard')
      useAIAction(action.id).catch(() => {})
    } catch {
      addToast('Copy failed', 'error')
    }
  }

  const handleApply = async () => {
    if (!onApply || !action) return
    setApplying(true)
    try {
      await onApply(action)
      useAIAction(action.id).catch(() => {})
      onClose()
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Apply failed', 'error')
    } finally {
      setApplying(false)
    }
  }

  const handleDismiss = () => {
    if (action?.id) {
      dismissAIAction(action.id).catch(() => {})
    }
    onClose()
  }

  if (!isOpen) return null

  const hasOutput = action && action.output && action.output.trim()
  const provider = action?.provider
  const isNoneProvider = provider === 'none'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleDismiss}
      />
      <div className="relative bg-surface rounded-xl w-full max-w-xl mx-4 shadow-2xl border border-th-border">
        <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
          <div className="flex items-center gap-2 text-th-text">
            <Sparkles size={16} className="text-brand-purple" />
            <h3 className="text-base font-semibold">{title}</h3>
          </div>
          <button
            onClick={handleDismiss}
            className="text-th-text-muted hover:text-th-text"
          >
            <X size={18} />
          </button>
        </div>
        <div className="px-5 py-5 min-h-[160px]">
          {loading && (
            <div className="flex items-center gap-2 text-th-text-muted text-sm">
              <Loader2 size={16} className="animate-spin" />
              Generating…
            </div>
          )}
          {!loading && error && (
            <p className="text-sm text-amber-400">{error}</p>
          )}
          {!loading && !error && (
            <>
              {isNoneProvider && (
                <div className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mb-3">
                  AI provider is set to "none" — output is empty by design.
                  Configure LLM_PROVIDER to use Ollama or Claude.
                </div>
              )}
              {hasOutput ? (
                <p className="text-sm text-th-text whitespace-pre-wrap leading-relaxed">
                  {action.output}
                </p>
              ) : (
                <p className="text-sm text-th-text-muted">
                  No output was generated.
                </p>
              )}
              {action?.tokens_used != null && action.tokens_used > 0 && (
                <p className="text-[11px] text-th-text-muted mt-3">
                  {action.provider} · {action.model} · {action.tokens_used} tokens ·{' '}
                  {action.duration_ms ? `${action.duration_ms} ms` : '—'}
                </p>
              )}
            </>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-th-border">
          <button
            onClick={handleDismiss}
            className="text-sm px-3 py-1.5 rounded-lg hover:bg-surface-hover text-th-text-secondary"
          >
            Dismiss
          </button>
          {hasOutput && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-surface-hover hover:bg-surface-hover/70 text-th-text"
            >
              <Copy size={14} /> Copy
            </button>
          )}
          {hasOutput && onApply && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold disabled:opacity-50"
            >
              {applying ? <Loader2 size={14} className="animate-spin" /> : null}
              {applyLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
