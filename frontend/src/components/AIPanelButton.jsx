import { Sparkles } from 'lucide-react'
import { useAIPanel } from '../context/AIPanelContext'

export default function AIPanelButton({
  mode = 'global',
  entityType = null,
  entityId = null,
  label = 'AI',
  variant = 'default',
}) {
  const { openPanel } = useAIPanel()
  const handleClick = () =>
    openPanel({ mode, entityType, entityId, conversationId: null })

  const baseClasses =
    'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors'
  const variantClasses =
    variant === 'header'
      ? 'text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover'
      : 'text-brand-purple hover:text-brand-purple-text bg-brand-purple/10 hover:bg-brand-purple/20'

  return (
    <button
      onClick={handleClick}
      className={`${baseClasses} ${variantClasses}`}
      title={mode === 'global' ? 'Open AI assistant' : `AI chat about this ${entityType}`}
    >
      <Sparkles size={15} />
      {label}
    </button>
  )
}
