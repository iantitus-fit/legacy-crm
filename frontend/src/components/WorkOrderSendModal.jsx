import { useEffect, useState } from 'react'
import { Mail, ShieldAlert, X } from 'lucide-react'
import { sendWorkOrder } from '../api/workOrders'
import { useToast } from '../context/ToastContext'

export default function WorkOrderSendModal({
  isOpen,
  estimateId,
  secret = false,
  defaultEmail = '',
  onClose,
  onSent,
}) {
  const { addToast } = useToast()
  const [recipientEmail, setRecipientEmail] = useState('')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setRecipientEmail(defaultEmail || '')
      setMessage('')
    }
  }, [isOpen, defaultEmail])

  if (!isOpen) return null

  const submit = async (e) => {
    e.preventDefault()
    if (!recipientEmail.trim()) return
    setSending(true)
    try {
      const result = await sendWorkOrder(estimateId, {
        recipientEmail: recipientEmail.trim(),
        secret,
        message: message.trim() || null,
      })
      addToast(`${result.wo_number} sent to ${result.sent_to}`)
      onSent?.(result)
    } catch (err) {
      addToast(
        err.response?.data?.detail || 'Failed to send work order',
        'error'
      )
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-surface rounded-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
          <h2 className="text-lg font-semibold text-th-text flex items-center gap-2">
            <Mail size={18} />
            {secret ? 'Send Secret Work Order' : 'Send Work Order'}
          </h2>
          <button
            onClick={onClose}
            disabled={sending}
            className="p-1.5 text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4">
          {secret && (
            <div className="flex items-start gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-200">
              <ShieldAlert size={14} className="shrink-0 mt-0.5" />
              <span>
                The customer's name, phone, and email will be redacted. The job
                address remains visible.
              </span>
            </div>
          )}

          <div>
            <label className="text-xs text-th-text-secondary font-medium block mb-1">
              Recipient email
            </label>
            <input
              type="email"
              required
              value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)}
              placeholder="crew@example.com"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-th-border-secondary text-th-text"
            />
          </div>

          <div>
            <label className="text-xs text-th-text-secondary font-medium block mb-1">
              Message (optional)
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              placeholder="Notes for the recipient…"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-th-border-secondary text-th-text resize-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={sending}
              className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={sending || !recipientEmail.trim()}
              className="px-4 py-2 text-sm rounded-lg bg-btn-primary-bg text-btn-primary-text hover:bg-btn-primary-hover disabled:opacity-50 flex items-center gap-1.5"
            >
              {sending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
