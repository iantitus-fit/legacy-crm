import { useEffect, useState } from 'react'
import { Plus, Users2, X } from 'lucide-react'
import { createCrew, deleteCrew, listCrews, updateCrew } from '../api/crews'
import { listEmployees } from '../api/employees'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import { COLOR_PRESETS } from '../utils/colorPresets'

function CrewModal({ crew, onSave, onClose }) {
  const isEdit = Boolean(crew)
  const [form, setForm] = useState({
    name: crew?.name || '',
    color: crew?.color || '#3B82F6',
    member_ids: crew?.members?.map((m) => m.id) || [],
  })
  const [employees, setEmployees] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployees(data.items))
      .catch(() => {})
  }, [])

  const toggleMember = (empId) => {
    setForm((prev) => ({
      ...prev,
      member_ids: prev.member_ids.includes(empId)
        ? prev.member_ids.filter((id) => id !== empId)
        : [...prev.member_ids, empId],
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (isEdit) {
        await onSave(crew.id, form)
      } else {
        await onSave(null, form)
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-surface rounded-xl w-full max-w-md p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">
            {isEdit ? 'Edit Crew' : 'Add Crew'}
          </h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text">
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4 text-sm text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Crew Name</label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
            />
          </div>

          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Color</label>
            <div className="flex flex-wrap items-center gap-2">
              {COLOR_PRESETS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setForm({ ...form, color: c })}
                  className={`w-7 h-7 rounded-full border-2 transition-all ${
                    form.color === c ? 'border-white scale-110' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: c }}
                  aria-label={`Select color ${c}`}
                />
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Members</label>
            <div className="max-h-48 overflow-y-auto space-y-1 bg-surface-hover/50 rounded-lg p-2">
              {employees.length === 0 ? (
                <p className="text-xs text-th-text-muted text-center py-2">No employees found</p>
              ) : (
                employees.map((emp) => (
                  <label
                    key={emp.id}
                    className="flex items-center gap-2.5 px-2 py-1.5 rounded hover:bg-th-border-secondary/50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={form.member_ids.includes(emp.id)}
                      onChange={() => toggleMember(emp.id)}
                      className="rounded border-th-border-secondary text-brand-purple focus:ring-brand-purple/50"
                    />
                    <div
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: emp.color || '#6B7280' }}
                    />
                    <span className="text-sm text-th-text">{emp.full_name}</span>
                    <span className="text-xs text-th-text-muted capitalize ml-auto">{emp.role}</span>
                  </label>
                ))
              )}
            </div>
          </div>

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
              disabled={saving}
              className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function CrewsPage() {
  const { addToast } = useToast()
  const [crews, setCrews] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalCrew, setModalCrew] = useState(undefined) // undefined=closed, null=create, object=edit
  const [deactivateId, setDeactivateId] = useState(null)

  const fetchCrews = () => {
    setLoading(true)
    listCrews({ perPage: 100 })
      .then((data) => setCrews(data.items))
      .catch(() => addToast('Failed to load crews', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchCrews()
  }, [])

  const handleSave = async (id, data) => {
    if (id) {
      await updateCrew(id, data)
      addToast('Crew updated')
    } else {
      await createCrew(data)
      addToast('Crew created')
    }
    setModalCrew(undefined)
    fetchCrews()
  }

  const handleDeactivate = async () => {
    if (!deactivateId) return
    try {
      await deleteCrew(deactivateId)
      setDeactivateId(null)
      addToast('Crew deactivated')
      fetchCrews()
    } catch {
      addToast('Failed to deactivate crew', 'error')
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-th-text">Crews</h1>
          <span className="text-xs px-2 py-1 rounded-full bg-surface text-th-text-secondary font-mono">
            {crews.length}
          </span>
        </div>
        <button
          onClick={() => setModalCrew(null)}
          className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2.5 rounded-lg text-sm transition-colors"
        >
          <Plus size={16} />
          Add Crew
        </button>
      </div>

      {loading ? (
        <LoadingSpinner centered />
      ) : crews.length === 0 ? (
        <EmptyState
          icon={Users2}
          title="No crews yet"
          description="Create your first crew to organize your team"
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {crews.map((crew) => (
            <div key={crew.id} className="bg-surface rounded-xl overflow-hidden">
              {/* Color bar */}
              <div className="h-1.5" style={{ backgroundColor: crew.color }} />

              <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base font-semibold text-th-text">{crew.name}</h3>
                  <span className={`text-xs font-medium ${crew.is_active ? 'text-emerald-400' : 'text-th-text-muted'}`}>
                    {crew.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {/* Members */}
                <div className="space-y-1.5 mb-4">
                  {crew.members.length === 0 ? (
                    <p className="text-xs text-th-text-muted">No members</p>
                  ) : (
                    crew.members.map((member) => (
                      <div key={member.id} className="flex items-center gap-2">
                        <div
                          className="w-2.5 h-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: member.color || '#6B7280' }}
                        />
                        <span className="text-sm text-th-text">{member.full_name}</span>
                      </div>
                    ))
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 border-t border-th-border pt-3">
                  <button
                    onClick={() => setModalCrew(crew)}
                    className="text-xs text-th-text-secondary hover:text-brand-purple transition-colors"
                  >
                    Edit
                  </button>
                  {crew.is_active && (
                    <button
                      onClick={() => setDeactivateId(crew.id)}
                      className="text-xs text-th-text-muted hover:text-red-400 transition-colors"
                    >
                      Deactivate
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalCrew !== undefined && (
        <CrewModal
          crew={modalCrew}
          onSave={handleSave}
          onClose={() => setModalCrew(undefined)}
        />
      )}

      <ConfirmDialog
        isOpen={deactivateId !== null}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivateId(null)}
        title="Deactivate Crew"
        message="This will deactivate the crew. It can be reactivated later."
        confirmLabel="Deactivate"
        variant="danger"
      />
    </div>
  )
}
