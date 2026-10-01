import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  Ban,
  Check,
  CheckCheck,
  Clock,
  Loader2,
  Phone,
  Send,
  Sparkles,
} from 'lucide-react'
import { getConversation, sendSms } from '../api/sms'
import { useToast } from '../context/ToastContext'

const PER_PAGE = 50

function formatTimestamp(iso) {
  const d = new Date(iso)
  const now = new Date()
  const sameDay =
    d.toDateString() === now.toDateString()
  if (sameDay) {
    return d.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })
  }
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function StatusIcon({ status, detail }) {
  switch (status) {
    case 'queued':
      return <Clock size={11} className="text-th-text-muted" title="Queued" />
    case 'sent':
      return <Check size={11} className="text-th-text-muted" title="Sent" />
    case 'delivered':
      return <CheckCheck size={11} className="text-sky-400" title="Delivered" />
    case 'failed':
    case 'undelivered':
      return (
        <AlertCircle
          size={11}
          className="text-red-400"
          title={detail || 'Failed'}
        />
      )
    default:
      return null
  }
}

function TriggerLabel({ triggeredBy }) {
  if (!triggeredBy || triggeredBy === 'manual') return null
  const map = {
    auto_new_lead: 'Auto-response',
    auto_new_lead_after_hours: 'Auto-response (after hours)',
    auto_estimate_sent: 'Estimate sent',
    auto_help_response: 'Help response',
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-th-text-muted uppercase tracking-wider mb-1">
      <Sparkles size={9} />
      {map[triggeredBy] || triggeredBy.replace(/_/g, ' ')}
    </span>
  )
}

export default function SmsConversationView({ contactId, contact }) {
  const { addToast } = useToast()
  const [messages, setMessages] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)
  const initialLoadRef = useRef(true)

  const optedOut = !!contact?.sms_opt_out
  const hasPhone = !!contact?.phone

  const fetchPage = useCallback(
    async (pageToLoad, mode) => {
      if (mode === 'more') setLoadingMore(true)
      else setLoading(true)
      try {
        const data = await getConversation(contactId, {
          page: pageToLoad,
          perPage: PER_PAGE,
        })
        // API returns newest-first; we reverse so the input is at the bottom
        // and oldest is at the top of the visible list.
        const ordered = [...data.items].reverse()
        setTotal(data.total)
        setMessages((prev) =>
          mode === 'more' ? [...ordered, ...prev] : ordered
        )
        setPage(pageToLoad)
      } catch (err) {
        addToast('Failed to load messages', 'error')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [contactId, addToast]
  )

  useEffect(() => {
    if (!hasPhone) {
      setLoading(false)
      return
    }
    fetchPage(1, 'first')
  }, [contactId, hasPhone, fetchPage])

  // Auto-scroll to bottom on first load and after sending.
  useEffect(() => {
    if (loading || !scrollRef.current) return
    if (initialLoadRef.current || !loadingMore) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
      initialLoadRef.current = false
    }
  }, [messages, loading, loadingMore])

  const handleSend = async () => {
    const trimmed = body.trim()
    if (!trimmed || sending) return
    setSending(true)
    try {
      const msg = await sendSms(contactId, trimmed)
      setMessages((prev) => [...prev, msg])
      setTotal((t) => t + 1)
      setBody('')
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to send message'
      addToast(detail, 'error')
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const loadedCount = messages.length
  const canLoadMore = loadedCount < total

  // -------------------- Empty states --------------------
  if (!hasPhone) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Phone size={32} className="text-th-text-muted mb-3" />
        <p className="text-sm font-medium text-th-text mb-1">
          No phone number on file
        </p>
        <p className="text-sm text-th-text-muted max-w-xs">
          Add a phone number on the Info tab to start texting this client.
        </p>
      </div>
    )
  }

  // -------------------- Main conversation --------------------
  return (
    <div className="flex flex-col h-[600px] max-h-[70vh]">
      {/* Opt-out banner */}
      {optedOut && (
        <div className="flex items-start gap-2 px-3 py-2 mb-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <Ban size={15} className="text-red-400 mt-0.5 shrink-0" />
          <div className="text-xs text-red-300">
            <p className="font-medium">This contact has opted out of text messages.</p>
            <p className="text-red-300/80 mt-0.5">
              They replied STOP. New texts cannot be sent until they reply START.
            </p>
          </div>
        </div>
      )}

      {/* Message list */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-1 sm:px-2 py-2 space-y-3"
      >
        {canLoadMore && (
          <div className="text-center">
            <button
              onClick={() => fetchPage(page + 1, 'more')}
              disabled={loadingMore}
              className="text-xs text-th-text-muted hover:text-th-text px-3 py-1 disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : `Load older messages (${total - loadedCount} more)`}
            </button>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-8 text-th-text-muted">
            <Loader2 size={16} className="animate-spin" />
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="text-center py-12 text-sm text-th-text-muted">
            No messages yet. Send the first one below.
          </div>
        )}

        {messages.map((msg) => {
          const outbound = msg.direction === 'outbound'
          return (
            <div
              key={msg.id}
              className={`flex ${outbound ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`flex flex-col ${
                  outbound ? 'items-end' : 'items-start'
                } max-w-[80%] sm:max-w-[70%]`}
              >
                <TriggerLabel triggeredBy={msg.triggered_by} />
                <div
                  className={`px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap break-words ${
                    outbound
                      ? 'bg-brand-purple text-white rounded-br-sm'
                      : 'bg-surface-hover text-th-text rounded-bl-sm'
                  }`}
                >
                  {msg.body}
                </div>
                <div
                  className={`flex items-center gap-1.5 mt-1 text-[10px] text-th-text-muted ${
                    outbound ? 'flex-row-reverse' : ''
                  }`}
                >
                  <span>{formatTimestamp(msg.created_at)}</span>
                  {outbound && (
                    <StatusIcon
                      status={msg.status}
                      detail={msg.status_detail}
                    />
                  )}
                  {outbound && msg.sent_by_name && (
                    <span className="text-th-text-muted/70">
                      · {msg.sent_by_name}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Input */}
      <div className="border-t border-th-border pt-3 mt-2">
        <div className="flex items-end gap-2">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={optedOut || sending}
            placeholder={
              optedOut
                ? 'Sending disabled — contact has opted out.'
                : 'Type a message…'
            }
            rows={1}
            className="flex-1 resize-none bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text placeholder:text-th-text-muted focus:outline-none focus:border-th-border-focus disabled:opacity-50 max-h-32"
            style={{ minHeight: '38px' }}
          />
          <button
            onClick={handleSend}
            disabled={optedOut || sending || !body.trim()}
            className="flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-brand-purple hover:bg-brand-purple/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors shrink-0"
          >
            {sending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Send size={15} />
            )}
            <span className="hidden sm:inline">
              {sending ? 'Sending' : 'Send'}
            </span>
          </button>
        </div>
        <p className="mt-1 text-[10px] text-th-text-muted">
          Press Enter to send. Shift+Enter for a new line.
        </p>
      </div>
    </div>
  )
}
