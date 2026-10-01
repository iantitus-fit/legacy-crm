import { useEffect, useMemo, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  TrendingUp,
  Trophy,
  Users,
  DollarSign,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getLeadSourceReport } from '../api/reports'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'

const PERIODS = [
  { key: 'all', label: 'All Time' },
  { key: '30d', label: 'Last 30 Days' },
  { key: '90d', label: 'Last 90 Days' },
  { key: 'ytd', label: 'Year to Date' },
  { key: 'custom', label: 'Custom Range' },
]

const PIE_COLORS = [
  '#7C3AED', // brand purple
  '#14B8A6', // brand teal
  '#F59E0B', // amber
  '#EF4444', // red
  '#3B82F6', // blue
  '#22C55E', // green
  '#EC4899', // pink
  '#A78BFA', // light purple
  '#06B6D4', // cyan
  '#F97316', // orange
]

const fmtMoney = (n) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n || 0)

const fmtPct = (n) => `${(n ?? 0).toFixed(1)}%`

function closeRateClass(rate) {
  if (rate < 5) return 'text-red-400'
  if (rate < 15) return 'text-amber-400'
  return 'text-emerald-400'
}

function SummaryCard({ label, value, sub, icon: Icon, tone = 'default' }) {
  const tones = {
    default: 'text-th-text',
    purple: 'text-brand-purple',
    green: 'text-emerald-400',
    amber: 'text-amber-400',
  }
  return (
    <div className="bg-surface rounded-xl p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-th-text-muted uppercase tracking-wider">
          {label}
        </span>
        {Icon && <Icon size={16} className={tones[tone] || tones.default} />}
      </div>
      <div className={`text-2xl font-semibold ${tones[tone] || tones.default}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-th-text-muted mt-1">{sub}</div>}
    </div>
  )
}

const COLUMNS = [
  { key: 'source', label: 'Source', align: 'left', numeric: false },
  { key: 'lead_count', label: 'Leads', align: 'right', numeric: true },
  { key: 'lead_percentage', label: '%', align: 'right', numeric: true },
  { key: 'estimate_count', label: 'Estimates', align: 'right', numeric: true },
  { key: 'approved_count', label: 'Approved', align: 'right', numeric: true },
  { key: 'close_rate', label: 'Close Rate', align: 'right', numeric: true },
  { key: 'avg_job_value', label: 'Avg Value', align: 'right', numeric: true },
  { key: 'total_collected', label: 'Revenue', align: 'right', numeric: true },
]

export default function LeadSourceReportPage() {
  const { addToast } = useToast()
  const [period, setPeriod] = useState('all')
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState('lead_count')
  const [sortDir, setSortDir] = useState('desc')

  const fetchReport = () => {
    if (period === 'custom' && (!customStart || !customEnd)) {
      setReport(null)
      setLoading(false)
      return
    }
    setLoading(true)
    getLeadSourceReport(period, customStart || undefined, customEnd || undefined)
      .then(setReport)
      .catch(() => addToast('Failed to load lead source report', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchReport()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, customStart, customEnd])

  const sortedSources = useMemo(() => {
    if (!report?.sources) return []
    const copy = [...report.sources]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (typeof av === 'string') {
        return sortDir === 'asc'
          ? av.localeCompare(bv)
          : bv.localeCompare(av)
      }
      const an = av ?? 0
      const bn = bv ?? 0
      return sortDir === 'asc' ? an - bn : bn - an
    })
    return copy
  }, [report, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      // Numeric columns default to desc (biggest first); strings to asc.
      const col = COLUMNS.find((c) => c.key === key)
      setSortDir(col?.numeric ? 'desc' : 'asc')
    }
  }

  // Derived summary metrics
  const topByVolume = useMemo(() => {
    if (!report?.sources?.length) return null
    return [...report.sources].sort((a, b) => b.lead_count - a.lead_count)[0]
  }, [report])
  const bestCloser = useMemo(() => {
    if (!report?.sources?.length) return null
    // Require at least 3 leads to avoid noise from single-lead sources.
    const eligible = report.sources.filter((s) => s.lead_count >= 3)
    if (!eligible.length) return null
    return [...eligible].sort((a, b) => b.close_rate - a.close_rate)[0]
  }, [report])

  // Chart data
  const volumeData = useMemo(() => {
    if (!report?.sources?.length) return []
    return report.sources
      .filter((s) => s.lead_count > 0)
      .map((s) => ({ name: s.source, value: s.lead_count }))
  }, [report])
  const rateData = useMemo(() => {
    if (!report?.sources?.length) return []
    return report.sources
      .filter((s) => s.lead_count >= 1)
      .map((s) => ({ name: s.source, value: s.close_rate }))
  }, [report])
  const avgValueData = useMemo(() => {
    if (!report?.sources?.length) return []
    return report.sources
      .filter((s) => s.approved_count > 0)
      .map((s) => ({ name: s.source, value: s.avg_job_value }))
  }, [report])

  const hasData =
    report &&
    ((report.sources && report.sources.length > 0) ||
      (report.unattributed && report.unattributed.lead_count > 0))

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-th-text">Lead Source Attribution</h1>
        <p className="text-th-text-muted text-sm mt-1">
          Where leads come from, how they convert, and what they're worth.
        </p>
      </div>

      {/* Period selector */}
      <div className="bg-surface rounded-xl p-4 mb-6 flex flex-wrap items-center gap-3">
        <span className="text-sm text-th-text-muted">Period:</span>
        <div className="flex flex-wrap gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                period === p.key
                  ? 'bg-brand-purple text-white'
                  : 'bg-surface-hover text-th-text-secondary hover:text-th-text'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex items-center gap-2 ml-auto">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="bg-page border border-th-border rounded-lg px-2 py-1 text-sm text-th-text"
            />
            <span className="text-xs text-th-text-muted">to</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="bg-page border border-th-border rounded-lg px-2 py-1 text-sm text-th-text"
            />
          </div>
        )}
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : !hasData ? (
        <div className="bg-surface rounded-xl p-12 text-center">
          <BarChart3 size={32} className="text-th-text-muted mx-auto mb-3" />
          <p className="text-th-text font-medium mb-1">No lead source data available</p>
          <p className="text-sm text-th-text-muted">
            Lead sources are populated when contacts are imported or created with a source.
          </p>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <SummaryCard
              label="Total Leads"
              value={report.total_leads}
              icon={Users}
              tone="purple"
            />
            <SummaryCard
              label="Total Revenue"
              value={fmtMoney(report.total_revenue)}
              icon={DollarSign}
              tone="green"
            />
            <SummaryCard
              label="Top Source"
              value={topByVolume?.source || '—'}
              sub={topByVolume ? `${topByVolume.lead_count} leads` : null}
              icon={Trophy}
              tone="amber"
            />
            <SummaryCard
              label="Best Closer"
              value={bestCloser?.source || '—'}
              sub={
                bestCloser ? `${fmtPct(bestCloser.close_rate)} close rate` : '(needs ≥3 leads)'
              }
              icon={TrendingUp}
              tone="green"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Table */}
            <div className="lg:col-span-2 bg-surface rounded-xl overflow-hidden">
              <div className="px-5 py-4 border-b border-th-border">
                <h2 className="text-sm font-semibold text-th-text uppercase tracking-wider">
                  Source breakdown
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-surface-hover">
                    <tr>
                      {COLUMNS.map((col) => {
                        const isActive = sortKey === col.key
                        const Icon = !isActive
                          ? ArrowUpDown
                          : sortDir === 'asc'
                          ? ArrowUp
                          : ArrowDown
                        return (
                          <th
                            key={col.key}
                            className={`px-3 py-2.5 text-xs font-semibold text-th-text-muted uppercase tracking-wider ${
                              col.align === 'right' ? 'text-right' : 'text-left'
                            }`}
                          >
                            <button
                              onClick={() => handleSort(col.key)}
                              className={`inline-flex items-center gap-1 ${
                                col.align === 'right' ? 'flex-row-reverse' : ''
                              } hover:text-th-text transition-colors`}
                            >
                              {col.label}
                              <Icon size={11} />
                            </button>
                          </th>
                        )
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedSources.map((s) => (
                      <tr
                        key={s.source}
                        className="border-t border-th-border hover:bg-surface-hover/40 transition-colors"
                      >
                        <td className="px-3 py-2.5 text-th-text font-medium">
                          {s.source}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {s.lead_count}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text-muted">
                          {fmtPct(s.lead_percentage)}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {s.estimate_count}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {s.approved_count}
                        </td>
                        <td
                          className={`px-3 py-2.5 text-right font-mono font-semibold ${closeRateClass(
                            s.close_rate
                          )}`}
                        >
                          {fmtPct(s.close_rate)}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {s.approved_count > 0 ? fmtMoney(s.avg_job_value) : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {fmtMoney(s.total_collected)}
                        </td>
                      </tr>
                    ))}
                    {report.unattributed?.lead_count > 0 && (
                      <tr className="border-t border-th-border text-th-text-muted italic">
                        <td className="px-3 py-2.5">Unattributed</td>
                        <td className="px-3 py-2.5 text-right font-mono">
                          {report.unattributed.lead_count}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                        <td className="px-3 py-2.5 text-right font-mono">—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Charts column */}
            <div className="space-y-6">
              <div className="bg-surface rounded-xl p-5">
                <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider mb-3">
                  Lead volume
                </h3>
                {volumeData.length === 0 ? (
                  <div className="text-sm text-th-text-muted py-8 text-center">
                    No leads in this period.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={volumeData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                      >
                        {volumeData.map((entry, i) => (
                          <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(15,13,26,0.95)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Legend
                        verticalAlign="bottom"
                        iconSize={8}
                        wrapperStyle={{ fontSize: 11 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="bg-surface rounded-xl p-5">
                <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider mb-3">
                  Close rate by source
                </h3>
                {rateData.length === 0 ? (
                  <div className="text-sm text-th-text-muted py-8 text-center">
                    No data.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={rateData} layout="vertical" margin={{ left: 4, right: 16 }}>
                      <XAxis
                        type="number"
                        tick={{ fontSize: 10, fill: 'currentColor' }}
                        axisLine={false}
                        tickLine={false}
                        domain={[0, 'auto']}
                        unit="%"
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11, fill: 'currentColor' }}
                        axisLine={false}
                        tickLine={false}
                        width={90}
                      />
                      <Tooltip
                        formatter={(v) => `${v.toFixed(1)}%`}
                        contentStyle={{
                          backgroundColor: 'rgba(15,13,26,0.95)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {rateData.map((entry) => (
                          <Cell
                            key={entry.name}
                            fill={
                              entry.value < 5
                                ? '#EF4444'
                                : entry.value < 15
                                ? '#F59E0B'
                                : '#22C55E'
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              <div className="bg-surface rounded-xl p-5">
                <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider mb-3">
                  Avg job value by source
                </h3>
                {avgValueData.length === 0 ? (
                  <div className="text-sm text-th-text-muted py-8 text-center">
                    No approved jobs in this period.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={avgValueData} layout="vertical" margin={{ left: 4, right: 16 }}>
                      <XAxis
                        type="number"
                        tick={{ fontSize: 10, fill: 'currentColor' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 11, fill: 'currentColor' }}
                        axisLine={false}
                        tickLine={false}
                        width={90}
                      />
                      <Tooltip
                        formatter={(v) => fmtMoney(v)}
                        contentStyle={{
                          backgroundColor: 'rgba(15,13,26,0.95)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Bar dataKey="value" fill="#7C3AED" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
