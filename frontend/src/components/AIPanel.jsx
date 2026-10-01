import { useEffect, useRef, useState } from 'react'
import { Loader2, Send, Sparkles, Sun, Trash2, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAIPanel } from '../context/AIPanelContext'
import { useToast } from '../context/ToastContext'
import {
  deleteConversation,
  getBriefingNarrative,
  getChips,
  getConversationMessages,
  listConversations,
  sendChat,
} from '../api/aiChat'

export default function AIPanel() {
  const {
    open,
    closePanel,
    mode,
    entityType,
    entityId,
    activeConversationId,
    setActiveConversationId,
  } = useAIPanel()
  const { addToast } = useToast()

  const [view, setView] = useState('list') // 'list' | 'chat'
  const [conversations, setConversations] = useState([])
  const [chips, setChips] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const messagesEndRef = useRef(null)

  // Reload conversation list + chips whenever the panel opens or scope changes.
  useEffect(() => {
    if (!open) return
    setLoadingList(true)
    Promise.all([
      listConversations(
        mode === 'entity' ? { entityType, entityId } : {},
      ),
      getChips(mode === 'entity' ? { entityType } : {}),
    ])
      .then(([convs, chipResp]) => {
        setConversations(convs.items || [])
        setChips(chipResp.items || [])
      })
      .catch(() => addToast('Failed to load conversations', 'error'))
      .finally(() => setLoadingList(false))
  }, [open, mode, entityType, entityId])

  // When activeConversationId changes, load its messages and switch to chat view.
  useEffect(() => {
    if (!open || !activeConversationId) {
      if (open && !activeConversationId) setView('list')
      return
    }
    setView('chat')
    setLoadingMessages(true)
    getConversationMessages(activeConversationId)
      .then((data) => setMessages(data.items || []))
      .catch(() => addToast('Failed to load messages', 'error'))
      .finally(() => setLoadingMessages(false))
  }, [open, activeConversationId])

  // Auto-scroll on new messages.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const startNew = () => {
    setActiveConversationId(null)
    setMessages([])
    setView('chat')
  }

  const send = async (text) => {
    const message = (text ?? input).trim()
    if (!message || sending) return
    setInput('')
    setSending(true)
    setMessages((prev) => [
      ...prev,
      {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      },
    ])
    try {
      const resp = await sendChat({
        conversationId: activeConversationId,
        entityType: mode === 'entity' ? entityType : null,
        entityId: mode === 'entity' ? entityId : null,
        message,
      })
      if (!activeConversationId) setActiveConversationId(resp.conversation_id)
      setMessages((prev) => [...prev, resp.message])
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Send failed', 'error')
    } finally {
      setSending(false)
    }
  }

  const openBriefing = async () => {
    setBriefingLoading(true)
    setActiveConversationId(null)
    setMessages([])
    setView('chat')
    try {
      const data = await getBriefingNarrative()
      setMessages([
        {
          id: 'briefing-1',
          role: 'assistant',
          content: data.narrative || '_(no briefing returned)_',
          created_at: new Date().toISOString(),
        },
      ])
    } catch (err) {
      const detail = err?.response?.data?.detail
      const msg =
        err?.response?.status === 503
          ? `Morning briefing requires an LLM provider. ${detail || ''}`
          : detail || 'Briefing failed'
      setMessages([
        {
          id: 'briefing-err',
          role: 'assistant',
          content: msg,
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setBriefingLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (activeConversationId === id) {
        setActiveConversationId(null)
        setMessages([])
        setView('list')
      }
    } catch {
      addToast('Delete failed', 'error')
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      <aside
        className="absolute right-0 top-0 bottom-0 w-full sm:w-[420px] bg-surface border-l border-th-border shadow-2xl flex flex-col pointer-events-auto"
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-th-border">
          <div className="flex items-center gap-2 text-th-text">
            <Sparkles size={16} className="text-brand-purple" />
            <h3 className="text-base font-semibold">
              {mode === 'entity'
                ? `AI · ${entityType}`
                : 'AI Assistant'}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {view === 'chat' && (
              <button
                onClick={() => {
                  setActiveConversationId(null)
                  setMessages([])
                  setView('list')
                }}
                className="text-xs text-th-text-muted hover:text-th-text"
              >
                ← Back
              </button>
            )}
            <button
              onClick={closePanel}
              className="text-th-text-muted hover:text-th-text"
              aria-label="Close AI panel"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        {view === 'list' && (
          <div className="flex-1 overflow-y-auto">
            {mode === 'global' && (
              <button
                onClick={openBriefing}
                disabled={briefingLoading}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm text-th-text bg-brand-purple/10 hover:bg-brand-purple/20 transition-colors border-b border-th-border disabled:opacity-50"
              >
                {briefingLoading ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Sun size={15} className="text-brand-purple" />
                )}
                Morning Briefing
              </button>
            )}

            <div className="px-4 py-3 border-b border-th-border">
              <button
                onClick={startNew}
                className="w-full text-sm bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-3 py-2 rounded-lg"
              >
                Start a new conversation
              </button>
            </div>

            {loadingList && (
              <div className="p-4 text-sm text-th-text-muted">Loading…</div>
            )}
            {!loadingList && conversations.length === 0 && (
              <div className="p-6 text-center text-sm text-th-text-muted">
                No conversations yet. Use a chip below to start one.
              </div>
            )}
            {!loadingList && conversations.map((c) => (
              <div
                key={c.id}
                className="flex items-start justify-between gap-2 px-4 py-3 border-b border-th-border hover:bg-surface-hover cursor-pointer"
                onClick={() => setActiveConversationId(c.id)}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-th-text truncate">
                    {c.title || 'Untitled'}
                  </p>
                  {c.last_message_preview && (
                    <p className="text-xs text-th-text-muted truncate mt-0.5">
                      {c.last_message_preview}
                    </p>
                  )}
                  <p className="text-[10px] text-th-text-muted mt-1">
                    {c.message_count} messages ·{' '}
                    {new Date(c.updated_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(c.id)
                  }}
                  className="text-th-text-muted hover:text-red-400 p-1"
                  aria-label="Delete conversation"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}

            {chips.length > 0 && (
              <div className="px-4 py-3 border-t border-th-border">
                <p className="text-[11px] uppercase tracking-wide text-th-text-muted mb-2">
                  Quick prompts
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {chips.map((chip) => (
                    <button
                      key={chip.label}
                      onClick={() => {
                        startNew()
                        setTimeout(() => send(chip.prompt), 0)
                      }}
                      className="text-xs px-2.5 py-1 rounded-full bg-surface-hover hover:bg-brand-purple/20 text-th-text-secondary"
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {view === 'chat' && (
          <>
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {loadingMessages && (
                <p className="text-sm text-th-text-muted">Loading…</p>
              )}
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={
                    m.role === 'user'
                      ? 'flex justify-end'
                      : 'flex justify-start'
                  }
                >
                  <div
                    className={
                      m.role === 'user'
                        ? 'max-w-[85%] rounded-2xl rounded-br-sm px-3 py-2 text-sm bg-brand-purple/15 text-th-text'
                        : 'max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm bg-surface-hover text-th-text prose prose-sm prose-invert max-w-none'
                    }
                  >
                    {m.role === 'assistant' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.content || '_(empty response — is LLM_PROVIDER configured?)_'}
                      </ReactMarkdown>
                    ) : (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-surface-hover rounded-2xl rounded-bl-sm px-3 py-2 text-sm text-th-text-muted">
                    <span className="inline-flex gap-1">
                      <span className="animate-bounce">·</span>
                      <span className="animate-bounce [animation-delay:0.15s]">·</span>
                      <span className="animate-bounce [animation-delay:0.3s]">·</span>
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {chips.length > 0 && messages.length === 0 && (
              <div className="px-4 pt-2 pb-1 flex flex-wrap gap-1.5">
                {chips.map((chip) => (
                  <button
                    key={chip.label}
                    onClick={() => send(chip.prompt)}
                    className="text-xs px-2.5 py-1 rounded-full bg-surface-hover hover:bg-brand-purple/20 text-th-text-secondary"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault()
                send()
              }}
              className="border-t border-th-border p-3 flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything…"
                disabled={sending}
                className="flex-1 bg-surface-hover text-th-text rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text rounded-lg p-2 disabled:opacity-50"
              >
                {sending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
              </button>
            </form>
          </>
        )}
      </aside>
    </div>
  )
}
