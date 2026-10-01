import { useEffect, useState } from 'react'
import { CheckSquare, Circle, Trash2 } from 'lucide-react'
import { createTask, deleteTask, toggleTask } from '../api/tasks'
import { listEmployees } from '../api/employees'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from './ConfirmDialog'

export default function JobTasksTab({ jobId, tasks, onRefresh }) {
  const { addToast } = useToast()
  const { user } = useAuth()
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteId, setDeleteId] = useState(null)
  const [employees, setEmployees] = useState([])

  useEffect(() => {
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => {
        setEmployees(data.items)
        if (user) setAssigneeId(String(user.id))
      })
      .catch(() => {})
  }, [user])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    try {
      await createTask({
        job_id: jobId,
        title: title.trim(),
        due_date: dueDate || undefined,
        assigned_to_user_id: assigneeId ? Number(assigneeId) : undefined,
        related_entity_type: 'job',
        related_entity_id: jobId,
      })
      setTitle('')
      setDueDate('')
      addToast('Task created')
      onRefresh()
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to create task', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (taskId) => {
    try {
      await toggleTask(taskId)
      onRefresh()
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
      onRefresh()
    } catch {
      addToast('Failed to delete task', 'error')
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return null
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    })
  }

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
          Add
        </button>
      </form>

      {/* Task List */}
      {tasks.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <CheckSquare size={24} className="text-th-text-muted mb-2" />
          <p className="text-th-text-muted text-sm">No tasks yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg group hover:bg-surface-hover/50 transition-colors ${
                task.is_overdue ? 'border-l-2 border-red-500' : ''
              }`}
            >
              <button
                onClick={() => handleToggle(task.id)}
                className="shrink-0"
              >
                {task.status === 'completed' ? (
                  <CheckSquare size={18} className="text-emerald-500" />
                ) : (
                  <Circle size={18} className="text-th-text-muted hover:text-brand-purple transition-colors" />
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

              {task.assigned_to_name && (
                <span className="text-xs text-th-text-muted">
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
          ))}
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
