import { useCallback, useEffect, useRef, useState } from 'react'
import { listContacts } from '../api/contacts'
import { listEmployees } from '../api/employees'
import { createAppointment, updateAppointment } from '../api/appointments'
import { useToast } from '../context/ToastContext'

const DURATION_OPTIONS = [
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
  { value: 90, label: '1.5 hours' },
  { value: 120, label: '2 hours' },
]

const TYPE_OPTIONS = [
  { value: 'quote', label: 'Quote' },
  { value: 'follow_up', label: 'Follow Up' },
  { value: 'inspection', label: 'Inspection' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'other', label: 'Other' },
]

export default function AppointmentModal({ isOpen, onClose, onSaved, appointment }) {
  const { addToast } = useToast()
  const isEditing = Boolean(appointment)
  const debounceRef = useRef(null)
  const contactDropdownRef = useRef(null)

  const [employees, setEmployees] = useState([])
  const [saving, setSaving] = useState(false)

  // Contact search state
  const [contactSearch, setContactSearch] = useState('')
  const [contactResults, setContactResults] = useState([])
  const [showContactDropdown, setShowContactDropdown] = useState(false)
  const [selectedContactId, setSelectedContactId] = useState(null)

  const [form, setForm] = useState({
    title: '',
    appointment_date: '',
    appointment_time: '',
    duration_minutes: 60,
    appointment_type: 'quote',
    assigned_to_user_id: '',
    location: '',
    notes: '',
  })

  // Initialize form when modal opens or appointment changes
  useEffect(() => {
    if (!isOpen) return

    setSaving(false)
    setContactResults([])
    setShowContactDropdown(false)

    if (appointment) {
      setForm({
        title: appointment.title || '',
        appointment_date: appointment.appointment_date || '',
        appointment_time: appointment.appointment_time || '',
        duration_minutes: appointment.duration_minutes || 60,
        appointment_type: appointment.appointment_type || 'quote',
        assigned_to_user_id: appointment.assigned_to_user_id ? String(appointment.assigned_to_user_id) : '',
        location: appointment.location || '',
        notes: appointment.notes || '',
      })
      setSelectedContactId(appointment.contact_id || null)
      setContactSearch(appointment.contact_name || '')
    } else {
      setForm({
        title: '',
        appointment_date: '',
        appointment_time: '',
        duration_minutes: 60,
        appointment_type: 'quote',
        assigned_to_user_id: '',
        location: '',
        notes: '',
      })
      setSelectedContactId(null)
      setContactSearch('')
    }

    // Fetch employees
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployees(data.items))
      .catch(() => setEmployees([]))
  }, [isOpen, appointment])

  // Close contact dropdown on outside click
  useEffect(() => {
    if (!showContactDropdown) return
    const handleClick = (e) => {
      if (contactDropdownRef.current && !contactDropdownRef.current.contains(e.target)) {
        setShowContactDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showContactDropdown])

  // Debounced contact search
  const searchContacts = useCallback((query) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (!query || query.length < 2) {
      setContactResults([])
      setShowContactDropdown(false)
      return
    }

    debounceRef.current = setTimeout(async () => {
      try {
        const data = await listContacts({ search: query, perPage: 10 })
        setContactResults(data.items)
        setShowContactDropdown(data.items.length > 0)
      } catch {
        setContactResults([])
        setShowContactDropdown(false)
      }
    }, 300)
  }, [])

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  const handleContactSearchChange = (e) => {
    const value = e.target.value
    setContactSearch(value)
    setSelectedContactId(null) // Clear selection when user types
    searchContacts(value)
  }

  const handleSelectContact = (contact) => {
    setContactSearch(contact.name)
    setSelectedContactId(contact.id)
    setShowContactDropdown(false)
    setContactResults([])
  }

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || !form.appointment_date) return

    setSaving(true)
    try {
      const payload = {
        title: form.title.trim(),
        appointment_date: form.appointment_date,
        duration_minutes: Number(form.duration_minutes),
        appointment_type: form.appointment_type,
      }

      if (form.appointment_time) {
        payload.appointment_time = form.appointment_time
      }
      if (selectedContactId) {
        payload.contact_id = selectedContactId
      }
      if (form.assigned_to_user_id) {
        payload.assigned_to_user_id = Number(form.assigned_to_user_id)
      }
      if (form.location.trim()) {
        payload.location = form.location.trim()
      }
      if (form.notes.trim()) {
        payload.notes = form.notes.trim()
      }

      if (isEditing) {
        await updateAppointment(appointment.id, payload)
        addToast('Appointment updated')
      } else {
        await createAppointment(payload)
        addToast('Appointment created')
      }

      onSaved()
      onClose()
    } catch (err) {
      addToast(
        err.response?.data?.detail || `Failed to ${isEditing ? 'update' : 'create'} appointment`,
        'error'
      )
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  const inputClass =
    'w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        className="absolute inset-0"
        onClick={onClose}
      />
      <div className="relative bg-surface rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-th-text mb-6">
          {isEditing ? 'Edit Appointment' : 'New Appointment'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={form.title}
              onChange={handleChange('title')}
              placeholder="e.g., Roof inspection at 123 Main St"
              className={`${inputClass} placeholder-gray-500`}
            />
          </div>

          {/* Contact Search */}
          <div ref={contactDropdownRef} className="relative">
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Contact
            </label>
            <input
              type="text"
              value={contactSearch}
              onChange={handleContactSearchChange}
              placeholder="Search contacts..."
              className={`${inputClass} placeholder-gray-500`}
            />
            {selectedContactId && (
              <span className="absolute right-3 top-[calc(50%+8px)] -translate-y-1/2 text-[10px] text-emerald-400 font-medium">
                Linked
              </span>
            )}

            {/* Contact search results dropdown */}
            {showContactDropdown && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-surface-hover border border-th-border-secondary rounded-lg shadow-xl z-10 max-h-40 overflow-y-auto">
                {contactResults.map((contact) => (
                  <button
                    key={contact.id}
                    type="button"
                    onClick={() => handleSelectContact(contact)}
                    className="w-full text-left px-3 py-2 text-sm text-th-text hover:bg-th-border-secondary transition-colors first:rounded-t-lg last:rounded-b-lg"
                  >
                    <span className="font-medium">{contact.name}</span>
                    {contact.phone && (
                      <span className="text-th-text-muted ml-2 text-xs">{contact.phone}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Date and Time row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                Date <span className="text-red-400">*</span>
              </label>
              <input
                type="date"
                required
                value={form.appointment_date}
                onChange={handleChange('appointment_date')}
                className={inputClass}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                Time
              </label>
              <input
                type="time"
                value={form.appointment_time}
                onChange={handleChange('appointment_time')}
                className={inputClass}
              />
            </div>
          </div>

          {/* Duration and Type row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                Duration
              </label>
              <select
                value={form.duration_minutes}
                onChange={handleChange('duration_minutes')}
                className={`${inputClass} appearance-none`}
              >
                {DURATION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                Type
              </label>
              <select
                value={form.appointment_type}
                onChange={handleChange('appointment_type')}
                className={`${inputClass} appearance-none`}
              >
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Assigned To */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Assigned To
            </label>
            <div className="relative">
              <select
                value={form.assigned_to_user_id}
                onChange={handleChange('assigned_to_user_id')}
                className={`${inputClass} appearance-none`}
              >
                <option value="">Unassigned</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.full_name}
                  </option>
                ))}
              </select>
              {/* Colored dot for selected employee */}
              {form.assigned_to_user_id && (() => {
                const selected = employees.find((e) => String(e.id) === form.assigned_to_user_id)
                if (!selected || !selected.color) return null
                return (
                  <span
                    className="absolute right-8 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full pointer-events-none"
                    style={{ backgroundColor: selected.color }}
                  />
                )
              })()}
            </div>
          </div>

          {/* Location */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Location
            </label>
            <input
              type="text"
              value={form.location}
              onChange={handleChange('location')}
              placeholder="e.g., 123 Main St, Kokomo, IN"
              className={`${inputClass} placeholder-gray-500`}
            />
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Notes
            </label>
            <textarea
              value={form.notes}
              onChange={handleChange('notes')}
              rows={3}
              placeholder="Additional details..."
              className={`${inputClass} placeholder-gray-500 resize-none`}
            />
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
              disabled={saving || !form.title.trim() || !form.appointment_date}
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
