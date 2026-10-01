import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Zap, MessageSquare, Mail } from 'lucide-react'
import { getAutomationDashboard } from '../api/automations'

function statusClass(status) {
  if (status === 'sent' || status === 'delivered')
    return 'text-emerald-400'
  if (status === 'failed') return 'text-red-400'
  if (status === 'skipped') return 'text-amber-400'
  return 'text-th-text-muted'
}

function relativeTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const diffMs = Date.now() - date.getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return date.toLocaleDateString()
}

export default function AutomationDashboardSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAutomationDashboard()
      .then(setData)
      .catch(() =>
        setData({
          active_sequences: 0,
          paused_sequences: 0,
          contacts_in_sequences: 0,
          messages_sent_7d: 0,
          messages_pending: 0,
          recent_activity: [],
        }),
      )
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-4 w-32 bg-surface-hover rounded mb-4" />
        <div className="grid grid-cols-3 gap-3 mb-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-surface-hover rounded" />
          ))}
        </div>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-6 bg-surface-hover rounded" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap size={15} className="text-brand-purple" />
          <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Automations
          </h3>
        </div>
        <Link
          to="/automations"
          className="text-xs text-brand-purple hover:underline inline-flex items-center gap-0.5"
        >
          Manage
          <ArrowRight size={11} />
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-page rounded-lg p-3 border border-th-border">
          <div className="text-xs text-th-text-muted mb-1">Active</div>
          <div className="text-xl font-bold text-th-text font-mono">
            {data?.active_sequences || 0}
          </div>
          {data?.paused_sequences > 0 && (
            <div className="text-xs text-th-text-muted mt-1">
              +{data.paused_sequences} paused
            </div>
          )}
        </div>
        <div className="bg-page rounded-lg p-3 border border-th-border">
          <div className="text-xs text-th-text-muted mb-1">Enrolled</div>
          <div className="text-xl font-bold text-th-text font-mono">
            {data?.contacts_in_sequences || 0}
          </div>
          <div className="text-xs text-th-text-muted mt-1">contacts</div>
        </div>
        <div className="bg-page rounded-lg p-3 border border-th-border">
          <div className="text-xs text-th-text-muted mb-1">Sent</div>
          <div className="text-xl font-bold text-th-text font-mono">
            {data?.messages_sent_7d || 0}
          </div>
          <div className="text-xs text-th-text-muted mt-1">last 7d</div>
        </div>
      </div>

      {data?.recent_activity?.length ? (
        <div>
          <div className="text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
            Recent
          </div>
          <div className="space-y-1.5">
            {data.recent_activity.map((a) => (
              <div
                key={a.log_id}
                className="flex items-center justify-between py-1 text-sm gap-2"
              >
                <div className="flex items-center gap-1.5 min-w-0 flex-1">
                  {a.channel === 'sms' ? (
                    <MessageSquare
                      size={11}
                      className="text-th-text-muted shrink-0"
                    />
                  ) : (
                    <Mail size={11} className="text-th-text-muted shrink-0" />
                  )}
                  <span className="text-th-text truncate">
                    {a.contact_name || 'Unknown'}
                  </span>
                  <span className="text-th-text-muted truncate">
                    · {a.sequence_name || '—'}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-xs">
                  <span
                    className={`font-medium font-mono ${statusClass(a.status)}`}
                  >
                    {a.status}
                  </span>
                  <span className="text-th-text-muted font-mono">
                    {relativeTime(a.timestamp)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-sm text-th-text-muted py-2">
          No automation activity yet.
        </div>
      )}
    </div>
  )
}
