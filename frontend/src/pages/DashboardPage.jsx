import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  Briefcase,
  Calendar,
  CheckSquare,
  DollarSign,
  Kanban,
  RefreshCw,
  UserPlus,
  Users,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getDashboardStats } from '../api/dashboard'
import { toggleTask } from '../api/tasks'
import { useToast } from '../context/ToastContext'
import DashboardTaskSection from '../components/DashboardTaskSection'
import DashboardInvoicesSection from '../components/DashboardInvoicesSection'
import DashboardLeadSourcesSection from '../components/DashboardLeadSourcesSection'
import AutomationDashboardSection from '../components/AutomationDashboardSection'

const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value || 0)
}

function StatCardSkeleton() {
  return (
    <div className="bg-surface rounded-xl p-6 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-20 bg-surface-hover rounded" />
        <div className="h-5 w-5 bg-surface-hover rounded" />
      </div>
      <div className="h-8 w-16 bg-surface-hover rounded" />
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="bg-surface rounded-xl p-6 animate-pulse space-y-4">
      <div className="h-5 w-32 bg-surface-hover rounded" />
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-4 bg-surface-hover rounded w-full" />
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchStats = () => {
    setLoading(true)
    setError(null)
    getDashboardStats()
      .then(setStats)
      .catch(() => setError('Failed to load dashboard data'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStats()
  }, [])

  const handleToggleTask = async (taskId) => {
    try {
      await toggleTask(taskId)
      fetchStats()
    } catch {
      addToast('Failed to update task', 'error')
    }
  }

  // Sprint 15c — prefer v2 counts (contacts + approved estimates) but
  // fall back to legacy job-based counts if the backend hasn't been
  // updated yet. pipeline_value_v2 > 0 is treated as "the backend
  // supports v2", since a 0-value v2 is indistinguishable from absence.
  const statCards = stats
    ? [
        {
          label: 'New Leads',
          value: String(stats.new_leads_count_v2 ?? stats.new_leads_count),
          icon: UserPlus,
          color: 'text-blue-400',
          link: '/pipelines/leads',
        },
        {
          label: 'Active Proposals',
          value: String(stats.active_proposals_count_v2 ?? stats.active_proposals_count),
          icon: Kanban,
          color: 'text-purple-400',
          link: '/pipelines/sales',
        },
        {
          label: 'Jobs In Progress',
          value: String(stats.jobs_in_progress_count_v2 ?? stats.jobs_in_progress_count),
          icon: Briefcase,
          color: 'text-emerald-400',
          link: '/pipelines/jobs',
        },
        {
          label: 'Pipeline Value',
          value: formatCurrency(
            stats.pipeline_value_v2 && Number(stats.pipeline_value_v2) > 0
              ? stats.pipeline_value_v2
              : stats.pipeline_value
          ),
          icon: DollarSign,
          color: 'text-brand-purple-text',
          link: '/pipelines/sales',
        },
      ]
    : []

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-th-text">
          Welcome, {user?.full_name}
        </h1>
        <p className="text-th-text-muted mt-1">Here&apos;s your business at a glance</p>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-red-400" />
            <p className="text-red-400 text-sm">{error}</p>
          </div>
          <button
            onClick={fetchStats}
            className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 transition-colors"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {loading
          ? [1, 2, 3, 4].map((i) => <StatCardSkeleton key={i} />)
          : statCards.map(({ label, value, icon: Icon, color, link }) => (
              <Link
                key={label}
                to={link}
                className="block hover:ring-1 hover:ring-brand-purple/30 rounded-xl transition-all"
              >
                <div className="bg-surface rounded-xl p-6">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm text-th-text-secondary">{label}</span>
                    <Icon size={20} className={color} />
                  </div>
                  <p className="text-2xl font-bold font-mono text-th-text">
                    {value}
                  </p>
                </div>
              </Link>
            ))}
      </div>

      {/* Sprint 14.5: Task columns — Past Due / Today / Future */}
      {!loading && stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <DashboardTaskSection
            title="Past Due"
            tone="past-due"
            tasks={stats.tasks_past_due || []}
            emptyText="No overdue tasks"
          />
          <DashboardTaskSection
            title="Today"
            tone="today"
            tasks={stats.tasks_today || []}
            emptyText="No tasks due today"
          />
          <DashboardTaskSection
            title="Future"
            tone="future"
            tasks={stats.tasks_future || []}
            emptyText="No upcoming tasks"
          />
        </div>
      )}

      {/* Sprint 18b — Lead source widget (top 3, last 30d) */}
      {!loading && stats && (
        <div className="mb-4">
          <DashboardLeadSourcesSection />
        </div>
      )}

      {/* Sprint 19c — Automations widget */}
      {!loading && stats && (
        <div className="mb-4">
          <AutomationDashboardSection />
        </div>
      )}

      {/* Sprint 14.5: Open invoices */}
      {!loading && stats && (
        <DashboardInvoicesSection invoices={stats.open_invoices || []} />
      )}

      {/* Bottom Section */}
      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <TableSkeleton />
          </div>
          <TableSkeleton />
        </div>
      ) : stats && stats.recent_jobs.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Jobs */}
          <div className="lg:col-span-2 bg-surface rounded-xl p-6">
            <h2 className="text-lg font-semibold text-th-text mb-4">
              Recent Jobs
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-th-border">
                    <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-3 py-2">
                      Contact
                    </th>
                    <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-3 py-2">
                      Pipeline
                    </th>
                    <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-3 py-2">
                      Stage
                    </th>
                    <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-3 py-2">
                      Value
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_jobs.map((job) => (
                    <tr
                      key={job.id}
                      onClick={() =>
                        navigate(job.contact_id ? `/contacts/${job.contact_id}` : `/jobs/${job.id}`)
                      }
                      className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                    >
                      <td className="px-3 py-2.5 text-sm font-medium text-th-text">
                        {job.contact_name || '-'}
                      </td>
                      <td className="px-3 py-2.5 text-sm text-th-text-secondary">
                        {job.pipeline_name || '-'}
                      </td>
                      <td className="px-3 py-2.5 text-sm text-th-text-secondary">
                        {job.stage_name || '-'}
                      </td>
                      <td className="px-3 py-2.5 text-sm text-right font-mono text-brand-purple">
                        {job.contract_value
                          ? formatCurrency(job.contract_value)
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right column: My Tasks Today + Team Summary */}
          <div className="space-y-6">
            {/* My Tasks Today */}
            <div className="bg-surface rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-th-text">My Tasks Today</h2>
                {stats.overdue_task_count > 0 && (
                  <Link
                    to="/tasks"
                    className="text-xs font-medium text-red-400 hover:text-red-300 transition-colors"
                  >
                    {stats.overdue_task_count} overdue
                  </Link>
                )}
              </div>

              {stats.my_tasks_today.length === 0 ? (
                <p className="text-sm text-th-text-muted py-4 text-center">
                  No tasks due today
                </p>
              ) : (
                <div className="space-y-1.5">
                  {stats.my_tasks_today.map((task) => (
                    <div key={task.id} className="flex items-center gap-2 group">
                      <button
                        onClick={() => handleToggleTask(task.id)}
                        className="shrink-0 w-4 h-4 rounded border border-th-border-secondary hover:border-brand-purple transition-colors"
                      />
                      <span className="text-sm text-th-text truncate">
                        {task.title}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Also show rest of week tasks below */}
              {stats.tasks_due_this_week.filter(
                (t) => !stats.my_tasks_today.some((today) => today.id === t.id)
              ).length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
                    This Week
                  </p>
                  <div className="space-y-1.5">
                    {stats.tasks_due_this_week
                      .filter(
                        (t) => !stats.my_tasks_today.some((today) => today.id === t.id)
                      )
                      .map((task) => (
                        <div key={task.id} className="flex items-center gap-2 group">
                          <button
                            onClick={() => handleToggleTask(task.id)}
                            className="shrink-0 w-4 h-4 rounded border border-th-border-secondary hover:border-brand-purple transition-colors"
                          />
                          <span className="text-sm text-th-text truncate">
                            {task.title}
                          </span>
                          <span className="text-[10px] text-th-text-muted font-mono ml-auto shrink-0">
                            {new Date(task.due_date + 'T00:00:00').toLocaleDateString(
                              'en-US',
                              { weekday: 'short' }
                            )}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>

            {/* Upcoming This Week */}
            {stats.upcoming_this_week && stats.upcoming_this_week.length > 0 && (
              <div className="bg-surface rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-th-text">Upcoming This Week</h2>
                  <Link
                    to="/calendars/job-schedule"
                    className="text-xs font-medium text-brand-purple hover:text-brand-purple-text transition-colors"
                  >
                    View Calendar
                  </Link>
                </div>
                <div className="space-y-2">
                  {stats.upcoming_this_week.map((item) => (
                    <Link
                      key={`${item.item_type}-${item.id}`}
                      to={item.link}
                      className="flex items-center gap-2.5 py-1.5 hover:bg-surface-hover/30 rounded px-2 -mx-2 transition-colors"
                    >
                      <span
                        className="shrink-0 w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: item.color || '#6B7280' }}
                      />
                      <span className="text-sm text-th-text truncate flex-1">
                        {item.title}
                      </span>
                      <span className="text-[10px] text-th-text-muted font-mono shrink-0">
                        {new Date(item.date + 'T00:00:00').toLocaleDateString('en-US', {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        item.item_type === 'job'
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'bg-purple-500/20 text-purple-400'
                      }`}>
                        {item.item_type === 'job' ? 'Job' : 'Appt'}
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Team Tasks Summary (admin only) */}
            {user?.role === 'admin' && stats.employee_task_counts.length > 0 && (
              <div className="bg-surface rounded-xl p-6">
                <h2 className="text-lg font-semibold text-th-text mb-4">
                  Team Tasks
                </h2>
                <div className="space-y-2">
                  {stats.employee_task_counts.map((emp) => (
                    <Link
                      key={emp.user_id}
                      to={`/tasks?employee=${emp.user_id}`}
                      className="flex items-center justify-between py-1.5 hover:bg-surface-hover/30 rounded px-2 -mx-2 transition-colors"
                    >
                      <span className="text-sm text-th-text">
                        {emp.full_name}
                      </span>
                      <div className="flex items-center gap-3">
                        {emp.due_today_count > 0 && (
                          <span className="text-xs text-brand-purple-text font-mono">
                            {emp.due_today_count} today
                          </span>
                        )}
                        <span className="text-xs text-th-text-muted font-mono">
                          {emp.open_count} open
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
