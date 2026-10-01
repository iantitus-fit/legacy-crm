import { useEffect, useState } from 'react'
import { X, Loader2 } from 'lucide-react'
import { createTask } from '../api/tasks'
import { listEmployees } from '../api/employees'
import { useToast } from '../context/ToastContext'

/**
 * Minimal task creation modal. Used by the FAB for one-off tasks not tied
 * to a job. Reuses `createTask` directly.
 */
export default function QuickCreateTaskModal({ onClose, onCreated }) {
  const { addToast } = useToast()
  const [saving, setSaving] = useState(false)
  const [employees, setEmployees] = useState([])
  const [form, setForm] = useState({
    title: '',
    due_date: '',
    assigned_to_user_id: '',
  })

  useEffect(() => {
    listEmployees()
      .then((data) => setEmployees(data.items || data))
      .catch(() => setEmployees([]))
  }, [])

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) {
      addToast('Title is required', 'error')
      return
    }
    setSaving(true)
    try {
      const task = await createTask({
        title: form.title.trim(),
        due_date: form.due_date || null,
        assigned_to_user_id: form.assigned_to_user_id
          ? Number(form.assigned_to_user_id)
          : null,
      })
      addToast('Task created')
      onCreated?.(task)
      onClose()
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create task', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4"
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        className="bg-surface border border-th-border rounded-lg w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-th-border">
          <h2 className="text-lg font-semibold text-th-text">New Task</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-th-text"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Title *</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => update('title', e.target.value)}
              autoFocus
              required
              className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Due date</label>
              <input
                type="date"
                value={form.due_date}
                onChange={(e) => update('due_date', e.target.value)}
                className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Assignee</label>
              <select
                value={form.assigned_to_user_id}
                onChange={(e) => update('assigned_to_user_id', e.target.value)}
                className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">Me</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.full_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t border-th-border">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-slate-400 hover:text-th-text"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-1.5 text-sm bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded disabled:opacity-50"
          >
            {saving && <Loader2 className="animate-spin" size={14} />}
            Create Task
          </button>
        </div>
      </form>
    </div>
  )
}
