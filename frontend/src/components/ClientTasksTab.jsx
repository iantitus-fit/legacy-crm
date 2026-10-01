import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Circle,
  Trash2,
} from 'lucide-react'
import { listContactTasks } from '../api/contacts'
import { listEmployees } from '../api/employees'
import { createTask, deleteTask, toggleTask } from '../api/tasks'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from './ConfirmDialog'

const SECTION_ORDER = ['overdue', 'upcoming', 'completed']

const SECTION_META = {
  overdue: {
    label: 'Overdue',
    headerClass: 'text-red-400',
    defaultOpen: true,
  },
  upcoming: {
    label: 'Upcoming',
    headerClass: 'text-th-text',
    defaultOpen: true,
  },
  completed: {
    label: 'Completed',
    headerClass: 'text-th-text-muted',
    defaultOpen: false,
  },
}

const formatDate = (dateStr) => {
  if (!dateStr) return null
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function EntityChip({ task, contactId }) {
  const { related_entity_type: type, related_entity_id: id, related_entity_label: label } = task

  if (!type || !id) return null
  if (type === 'contact' && Number(id) === Number(contactId)) {
    // No link — user is already on this contact's profile
    return null
  }

  const display =
    type === 'estimate'
      ? `EST-${String(id).padStart(4, '0')}`
      : type === 'job'
      ? label || `Job #${id}`
      : label || type

  const to =
    type === 'estimate'
      ? `/estimates/${id}`
      : type === 'job'
      ? `/jobs/${id}`
      : null

  const className =
    'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-surface-hover text-th-text-secondary hover:text-th-text transition-colors'

  if (!to) {
    return <span className={className}>{display}</span>
  }
  return (
    <Link to={to} onClick={(e) => e.stopPropagation()} className={className}>
      {display}
    </Link>
  )
}

export default function ClientTasksTab({ contactId, onTasksChange }) {
  const { addToast } = useToast()
  const { user } = useAuth()
  const [tasks, setTasks] = useState([])
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteId, setDeleteId] = useState(null)
  const [openSections, setOpenSections] = useState({
    overdue: true,
    upcoming: true,
    completed: false,
  })

  const load = async () => {
    setLoading(true)
    try {
      const data = await listContactTasks(contactId)
      setTasks(data || [])
      onTasksChange?.((data || []).filter((t) => t.status !== 'completed').length)
    } catch {
      addToast('Failed to load tasks', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployees(data.items || []))
      .catch(() => setEmployees([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId])

  useEffect(() => {
    if (user) setAssigneeId(String(user.id))
  }, [user])

  const sections = useMemo(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const buckets = { overdue: [], upcoming: [], completed: [] }
    for (const t of tasks) {
      if (t.status === 'completed') {
        buckets.completed.push(t)
      } else if (
        t.due_date &&
        new Date(`${t.due_date}T00:00:00`) < today
      ) {
        buckets.overdue.push(t)
      } else {
        buckets.upcoming.push(t)
      }
    }
    // Completed: most recent first (use created_at as a proxy since we
    // don't track completed_at)
    buckets.completed.sort((a, b) => {
      const ad = a.created_at ? new Date(a.created_at).getTime() : 0
      const bd = b.created_at ? new Date(b.created_at).getTime() : 0
      return bd - ad
    })
    return buckets
  }, [tasks])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    try {
      await createTask({
        title: title.trim(),
        due_date: dueDate || undefined,
        assigned_to_user_id: assigneeId ? Number(assigneeId) : undefined,
        related_entity_type: 'contact',
        related_entity_id: Number(contactId),
      })
      setTitle('')
      setDueDate('')
      addToast('Task created')
      load()
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to create task', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (taskId) => {
    try {
      await toggleTask(taskId)
      load()
    } catch {
      addToast('Failed to update task', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTask(deleteId)
      setDeleteId(null)
      addToast('Task deleted')
      load()
    } catch {
      addToast('Failed to delete task', 'error')
    }
  }

  const toggleSection = (key) =>
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }))

  if (loading) {
    return (
      <div className="text-th-text-muted text-sm py-6 text-center">
        Loading tasks...
      </div>
    )
  }

  const renderTask = (task) => (
    <div
      key={task.id}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg group hover:bg-surface-hover/50 transition-colors ${
        task.is_overdue ? 'border-l-2 border-red-500' : ''
      }`}
    >
      <button onClick={() => handleToggle(task.id)} className="shrink-0">
        {task.status === 'completed' ? (
          <CheckSquare size={18} className="text-emerald-500" />
        ) : (
          <Circle
            size={18}
            className="text-th-text-muted hover:text-brand-purple transition-colors"
          />
        )}
      </button>

      <span
        className={`flex-1 text-sm ${
          task.status === 'completed'
            ? 'line-through text-th-text-muted'
            : 'text-th-text'
        }`}
      >
        {task.title}
      </span>

      <EntityChip task={task} contactId={contactId} />

      {task.assigned_to_name && (
        <span className="text-xs text-th-text-muted whitespace-nowrap">
          {task.assigned_to_name.split(' ')[0]}
        </span>
      )}

      {task.due_date && (
        <span
          className={`text-xs font-mono ${
            task.is_overdue ? 'text-red-400' : 'text-th-text-muted'
          }`}
        >
          {formatDate(task.due_date)}
        </span>
      )}

      <button
        onClick={() => setDeleteId(task.id)}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )

  return (
    <div>
      {/* Add Task Form */}
      <form onSubmit={handleAdd} className="flex items-center gap-3 mb-4 flex-wrap">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a task..."
          className="flex-1 min-w-[200px] bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
        />
        <select
          value={assigneeId}
          onChange={(e) => setAssigneeId(e.target.value)}
          className="bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
        >
          <option value="">Unassigned</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.full_name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          className="bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
        />
        <button
          type="submit"
          disabled={saving || !title.trim()}
          className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          Add Task
        </button>
      </form>

      {tasks.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <CheckSquare size={24} className="text-th-text-muted mb-2" />
          <p className="text-th-text-muted text-sm">No tasks yet</p>
        </div>
      ) : (
        <div className="space-y-4">
          {SECTION_ORDER.map((key) => {
            const items = sections[key]
            if (items.length === 0) return null
            const meta = SECTION_META[key]
            const isOpen = openSections[key]
            return (
              <div key={key}>
                <button
                  onClick={() => toggleSection(key)}
                  className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider mb-2 ${meta.headerClass}`}
                >
                  {isOpen ? (
                    <ChevronDown size={14} />
                  ) : (
                    <ChevronRight size={14} />
                  )}
                  {meta.label}
                  <span className="text-th-text-muted font-normal normal-case tracking-normal">
                    ({items.length})
                  </span>
                </button>
                {isOpen && <div className="space-y-1">{items.map(renderTask)}</div>}
              </div>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Delete Task"
        message="Are you sure you want to delete this task?"
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
