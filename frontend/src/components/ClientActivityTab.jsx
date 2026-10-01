import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity } from 'lucide-react'
import { listContactActivity } from '../api/contacts'
import { useToast } from '../context/ToastContext'

const TYPE_STYLES = {
  payment_received: { dot: 'bg-emerald-500', ring: 'ring-emerald-500/30' },
  estimate_approved: { dot: 'bg-emerald-500', ring: 'ring-emerald-500/30' },
  invoice_paid: { dot: 'bg-emerald-500', ring: 'ring-emerald-500/30' },
  estimate_created: { dot: 'bg-blue-500', ring: 'ring-blue-500/30' },
  invoice_created: { dot: 'bg-blue-500', ring: 'ring-blue-500/30' },
  change_order_created: { dot: 'bg-blue-500', ring: 'ring-blue-500/30' },
  note_added: { dot: 'bg-purple-500', ring: 'ring-purple-500/30' },
  task_created: { dot: 'bg-purple-500', ring: 'ring-purple-500/30' },
  estimate_sent: { dot: 'bg-orange-500', ring: 'ring-orange-500/30' },
  estimate_viewed: { dot: 'bg-orange-500', ring: 'ring-orange-500/30' },
  estimate_rejected: { dot: 'bg-red-500', ring: 'ring-red-500/30' },
  estimate_changes_requested: {
    dot: 'bg-orange-500',
    ring: 'ring-orange-500/30',
  },
}

const DEFAULT_STYLE = { dot: 'bg-gray-500', ring: 'ring-gray-500/30' }

const ENTITY_LINK = {
  estimate: (id) => `/estimates/${id}`,
  invoice: (id) => `/invoices/${id}`,
  job: (id) => `/jobs/${id}`,
}

function formatRelative(ts) {
  if (!ts) return ''
  const date = new Date(ts)
  const diffMs = Date.now() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatExact(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function ClientActivityTab({ contactId }) {
  const { addToast } = useToast()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    listContactActivity(contactId)
      .then((data) => {
        if (!cancelled) setEvents(data || [])
      })
      .catch(() => {
        if (!cancelled) addToast('Failed to load activity', 'error')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId])

  if (loading) {
    return (
      <div className="text-th-text-muted text-sm py-6 text-center">
        Loading activity...
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-center">
        <Activity size={24} className="text-th-text-muted mb-2" />
        <p className="text-th-text-muted text-sm">
          No activity recorded for this client yet.
        </p>
      </div>
    )
  }

  return (
    <ol className="relative border-l border-th-border ml-3">
      {events.map((e, idx) => {
        const style = TYPE_STYLES[e.type] || DEFAULT_STYLE
        const linkBuilder = ENTITY_LINK[e.entity_type]
        const linkTo =
          linkBuilder && e.entity_id ? linkBuilder(e.entity_id) : null
        return (
          <li key={`${e.type}-${e.entity_type}-${e.entity_id}-${e.timestamp}-${idx}`} className="ml-5 pb-5">
            <span
              className={`absolute -left-[7px] flex h-3.5 w-3.5 items-center justify-center rounded-full ring-4 ${style.dot} ${style.ring}`}
              aria-hidden
            />
            <div className="flex items-baseline gap-2 flex-wrap">
              {linkTo ? (
                <Link
                  to={linkTo}
                  className="text-sm text-th-text hover:text-brand-purple transition-colors"
                >
                  {e.description}
                </Link>
              ) : (
                <span className="text-sm text-th-text">{e.description}</span>
              )}
              <span
                className="text-xs text-th-text-muted font-mono"
                title={formatExact(e.timestamp)}
              >
                {formatRelative(e.timestamp)}
              </span>
            </div>
            {e.actor && (
              <p className="text-xs text-th-text-muted mt-0.5">by {e.actor}</p>
            )}
          </li>
        )
      })}
    </ol>
  )
}
