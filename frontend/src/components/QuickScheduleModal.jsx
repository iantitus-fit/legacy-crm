import { useEffect, useState } from 'react'
import { listCrews } from '../api/crews'
import { scheduleJob } from '../api/jobs'
import { useToast } from '../context/ToastContext'

export default function QuickScheduleModal({ isOpen, onClose, jobId, onScheduled }) {
  const { addToast } = useToast()
  const [crews, setCrews] = useState([])
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    scheduled_date: '',
    scheduled_end_date: '',
    crew_id: '',
  })

  useEffect(() => {
    if (!isOpen) return
    // Reset form when modal opens
    setForm({ scheduled_date: '', scheduled_end_date: '', crew_id: '' })
    setSaving(false)

    // Fetch active crews
    listCrews({ isActive: true, perPage: 100 })
      .then((data) => setCrews(data.items))
      .catch(() => setCrews([]))
  }, [isOpen])

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.scheduled_date) return

    setSaving(true)
    try {
      const payload = {
        scheduled_date: form.scheduled_date,
      }
      if (form.scheduled_end_date) {
        payload.scheduled_end_date = form.scheduled_end_date
      }
      if (form.crew_id) {
        payload.crew_id = Number(form.crew_id)
      }

      await scheduleJob(jobId, payload)
      addToast('Job scheduled successfully')
      onScheduled()
      onClose()
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to schedule job', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        className="absolute inset-0"
        onClick={onClose}
      />
      <div className="relative bg-surface rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
        <h2 className="text-lg font-semibold text-th-text mb-6">Schedule Job</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Scheduled Date */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Start Date <span className="text-red-400">*</span>
            </label>
            <input
              type="date"
              required
              value={form.scheduled_date}
              onChange={handleChange('scheduled_date')}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              End Date
            </label>
            <input
              type="date"
              value={form.scheduled_end_date}
              onChange={handleChange('scheduled_end_date')}
              min={form.scheduled_date || undefined}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            />
          </div>

          {/* Crew */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Crew
            </label>
            <div className="relative">
              <select
                value={form.crew_id}
                onChange={handleChange('crew_id')}
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus appearance-none"
              >
                <option value="">No crew assigned</option>
                {crews.map((crew) => (
                  <option key={crew.id} value={crew.id}>
                    {crew.name}
                  </option>
                ))}
              </select>
              {/* Colored dot indicator for selected crew */}
              {form.crew_id && (() => {
                const selected = crews.find((c) => String(c.id) === form.crew_id)
                if (!selected) return null
                return (
                  <span
                    className="absolute right-8 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full pointer-events-none"
                    style={{ backgroundColor: selected.color || '#6B7280' }}
                  />
                )
              })()}
            </div>
            {/* Crew color legend below dropdown */}
            {crews.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {crews.map((crew) => (
                  <span key={crew.id} className="flex items-center gap-1 text-[11px] text-th-text-muted">
                    <span
                      className="w-2 h-2 rounded-full inline-block"
                      style={{ backgroundColor: crew.color || '#6B7280' }}
                    />
                    {crew.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !form.scheduled_date}
              className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
