import { useState } from 'react'
import { X, Loader2 } from 'lucide-react'
import { createLead } from '../api/leads'
import { useToast } from '../context/ToastContext'

/**
 * Minimal lead creation modal used by the FAB and the Lead pipeline button.
 * Creates a lead via POST /api/leads. On success, calls onCreated(lead).
 */
export default function QuickCreateLeadModal({ onClose, onCreated }) {
  const { addToast } = useToast()
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    source: '',
    description: '',
  })

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.contact_name.trim()) {
      addToast('Contact name is required', 'error')
      return
    }
    setSaving(true)
    try {
      const lead = await createLead({
        contact_name: form.contact_name.trim(),
        contact_phone: form.contact_phone.trim() || null,
        contact_email: form.contact_email.trim() || null,
        source: form.source.trim() || null,
        description: form.description.trim() || null,
      })
      addToast('Lead created')
      onCreated?.(lead)
      onClose()
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create lead', 'error')
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
          <h2 className="text-lg font-semibold text-th-text">New Lead</h2>
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
            <label className="block text-xs text-slate-400 mb-1">Name *</label>
            <input
              type="text"
              value={form.contact_name}
              onChange={(e) => update('contact_name', e.target.value)}
              autoFocus
              required
              className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Phone</label>
              <input
                type="tel"
                value={form.contact_phone}
                onChange={(e) => update('contact_phone', e.target.value)}
                className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Email</label>
              <input
                type="email"
                value={form.contact_email}
                onChange={(e) => update('contact_email', e.target.value)}
                className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Source</label>
            <input
              type="text"
              value={form.source}
              onChange={(e) => update('source', e.target.value)}
              placeholder="e.g. Referral, Website"
              className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-page border border-th-border rounded text-th-text focus:outline-none focus:border-th-border-focus"
            />
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
            Create Lead
          </button>
        </div>
      </form>
    </div>
  )
}
