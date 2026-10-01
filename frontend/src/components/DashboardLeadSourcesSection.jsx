import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BarChart3 } from 'lucide-react'
import { getLeadSourceSummary } from '../api/reports'

function closeRateClass(rate) {
  if (rate < 5) return 'text-red-400'
  if (rate < 15) return 'text-amber-400'
  return 'text-emerald-400'
}

export default function DashboardLeadSourcesSection() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getLeadSourceSummary('30d')
      .then(setSummary)
      .catch(() => setSummary({ sources: [], total_leads: 0 }))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="bg-surface rounded-xl p-5 animate-pulse">
        <div className="h-4 w-32 bg-surface-hover rounded mb-4" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-6 bg-surface-hover rounded" />
          ))}
        </div>
      </div>
    )
  }

  const top3 = (summary?.sources || []).slice(0, 3)

  return (
    <div className="bg-surface rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 size={15} className="text-brand-purple" />
          <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Lead Sources
          </h3>
          <span className="text-xs text-th-text-muted">last 30d</span>
        </div>
        <Link
          to="/reports/lead-sources"
          className="text-xs text-brand-purple hover:underline inline-flex items-center gap-0.5"
        >
          View full report
          <ArrowRight size={11} />
        </Link>
      </div>

      {top3.length === 0 ? (
        <div className="text-sm text-th-text-muted py-3">
          No new leads in the last 30 days.
        </div>
      ) : (
        <div className="space-y-2">
          {top3.map((s) => (
            <div
              key={s.source}
              className="flex items-center justify-between py-1.5"
            >
              <div className="text-sm text-th-text font-medium truncate">
                {s.source}
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="font-mono text-th-text">
                  {s.lead_count} {s.lead_count === 1 ? 'lead' : 'leads'}
                </span>
                <span
                  className={`font-mono font-semibold ${closeRateClass(s.close_rate)}`}
                >
                  {s.close_rate.toFixed(1)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
