import { createContext, useCallback, useContext, useState } from 'react'

const AIPanelContext = createContext(null)

export function AIPanelProvider({ children }) {
  const [open, setOpen] = useState(false)
  // mode: 'global' | 'entity'; entityType: 'contact' | 'estimate' | null
  const [mode, setMode] = useState('global')
  const [entityType, setEntityType] = useState(null)
  const [entityId, setEntityId] = useState(null)
  // Track the currently active conversation so opening the panel from
  // another page can resume it.
  const [activeConversationId, setActiveConversationId] = useState(null)

  const openPanel = useCallback((opts = {}) => {
    setMode(opts.mode || 'global')
    setEntityType(opts.entityType || null)
    setEntityId(opts.entityId ?? null)
    if (opts.conversationId !== undefined) {
      setActiveConversationId(opts.conversationId)
    }
    setOpen(true)
  }, [])

  const closePanel = useCallback(() => setOpen(false), [])

  const value = {
    open,
    mode,
    entityType,
    entityId,
    activeConversationId,
    setActiveConversationId,
    openPanel,
    closePanel,
  }
  return (
    <AIPanelContext.Provider value={value}>{children}</AIPanelContext.Provider>
  )
}

export function useAIPanel() {
  const ctx = useContext(AIPanelContext)
  if (!ctx) throw new Error('useAIPanel must be used inside <AIPanelProvider>')
  return ctx
}
