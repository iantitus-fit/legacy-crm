import { Link, useNavigate } from 'react-router-dom'
import { AlertTriangle, CalendarCheck2, CalendarClock } from 'lucide-react'

const ICON_BY_TONE = {
  'past-due': AlertTriangle,
  today: CalendarCheck2,
  future: CalendarClock,
}

const TONE_CLASSES = {
  'past-due': 'text-red-400',
  today: 'text-brand-purple-text',
  future: 'text-blue-400',
}

function formatDueDate(iso) {
  if (!iso) return ''
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * One column in the dashboard task rows: title, count badge, list of up to
 * 5 tasks, "View all" link.
 *
 * Props:
 * - title: section header text
 * - tone: 'past-due' | 'today' | 'future'
 * - tasks: TaskDueResponse[]
 * - emptyText: placeholder when no tasks
 */
export default function DashboardTaskSection({ title, tone, tasks = [], emptyText = 'No tasks' }) {
  const Icon = ICON_BY_TONE[tone]
  const toneClass = TONE_CLASSES[tone]
  const navigate = useNavigate()

  const handleRowClick = (task) => {
    if (task.job_id) navigate(`/jobs/${task.job_id}`)
    else navigate('/tasks')
  }

  return (
    <div className="bg-surface rounded-xl p-4 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={16} className={toneClass} />}
          <h3 className="text-sm font-semibold text-th-text">{title}</h3>
        </div>
        <span className={`text-xs font-mono px-2 py-0.5 rounded-full bg-surface-hover ${toneClass}`}>
          {tasks.length}
        </span>
      </div>

      {tasks.length === 0 ? (
        <p className="text-xs text-th-text-muted py-4 text-center">{emptyText}</p>
      ) : (
        <ul className="space-y-1.5 flex-1">
          {tasks.slice(0, 5).map((task) => (
            <li key={task.id}>
              <button
                type="button"
                onClick={() => handleRowClick(task)}
                className="w-full text-left px-2 py-1.5 rounded hover:bg-surface-hover/50 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-th-text truncate flex-1">
                    {task.title}
                  </span>
                  <span className="text-[10px] text-th-text-muted font-mono shrink-0">
                    {formatDueDate(task.due_date)}
                  </span>
                </div>
                {task.job_address && (
                  <div className="text-xs text-th-text-muted truncate mt-0.5">
                    {task.job_address}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Link
        to="/tasks"
        className="text-xs text-brand-purple hover:text-brand-purple-text transition-colors mt-3 self-start"
      >
        View all →
      </Link>
    </div>
  )
}
