import { useEffect, useState } from 'react'
import { Plus, Search, Users, X } from 'lucide-react'
import { createEmployee, deleteEmployee, listEmployees, updateEmployee } from '../api/employees'
import { useToast } from '../context/ToastContext'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'
import { COLOR_PRESETS } from '../utils/colorPresets'

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'staff', label: 'Staff' },
  { value: 'crew', label: 'Crew' },
]

function EmployeeModal({ employee, onSave, onClose }) {
  const isEdit = Boolean(employee)
  const [form, setForm] = useState({
    full_name: employee?.full_name || '',
    email: employee?.email || '',
    password: '',
    role: employee?.role || 'staff',
    phone: employee?.phone || '',
    color: employee?.color || '#3B82F6',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = { ...form }
      if (isEdit) {
        delete payload.password
        await onSave(employee.id, payload)
      } else {
        await onSave(null, payload)
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
            {isEdit ? 'Edit Employee' : 'Add Employee'}
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
            <label className="block text-xs text-th-text-secondary mb-1">Full Name</label>
            <input
              type="text"
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
            />
          </div>

          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
            />
          </div>

          {!isEdit && (
            <div>
              <label className="block text-xs text-th-text-secondary mb-1">Password</label>
              <input
                type="password"
                required
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-th-text-secondary mb-1">Phone</label>
            <input
              type="text"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
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

export default function EmployeesPage() {
  const { addToast } = useToast()
  const [employees, setEmployees] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modalEmployee, setModalEmployee] = useState(undefined) // undefined=closed, null=create, object=edit
  const [deactivateId, setDeactivateId] = useState(null)
  const perPage = 25

  const fetchEmployees = () => {
    setLoading(true)
    listEmployees({ search: search || undefined, page, perPage })
      .then((data) => {
        setEmployees(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load employees', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchEmployees()
  }, [search, page])

  const handleSave = async (id, data) => {
    if (id) {
      await updateEmployee(id, data)
      addToast('Employee updated')
    } else {
      await createEmployee(data)
      addToast('Employee created')
    }
    setModalEmployee(undefined)
    fetchEmployees()
  }

  const handleDeactivate = async () => {
    if (!deactivateId) return
    try {
      await deleteEmployee(deactivateId)
      setDeactivateId(null)
      addToast('Employee deactivated')
      fetchEmployees()
    } catch {
      addToast('Failed to deactivate employee', 'error')
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-th-text">Employees</h1>
          <span className="text-xs px-2 py-1 rounded-full bg-surface text-th-text-secondary font-mono">
            {total}
          </span>
        </div>
        <button
          onClick={() => setModalEmployee(null)}
          className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2.5 rounded-lg text-sm transition-colors"
        >
          <Plus size={16} />
          Add Employee
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-sm">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted" />
        <input
          type="text"
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="w-full bg-surface border border-th-border rounded-lg pl-9 pr-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
        />
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner centered />
      ) : employees.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No employees found"
          description={search ? 'Try a different search' : 'Add your first employee to get started'}
        />
      ) : (
        <div className="bg-surface rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-th-border">
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Name
                </th>
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Email
                </th>
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Role
                </th>
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Phone
                </th>
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Status
                </th>
                <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr
                  key={emp.id}
                  className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: emp.color || '#6B7280' }}
                      />
                      <span className="text-sm font-medium text-th-text">{emp.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-secondary">{emp.email}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-hover text-th-text capitalize">
                      {emp.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-secondary">{emp.phone || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${emp.is_active ? 'text-emerald-400' : 'text-th-text-muted'}`}>
                      {emp.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setModalEmployee(emp)}
                        className="text-xs text-th-text-secondary hover:text-brand-purple transition-colors"
                      >
                        Edit
                      </button>
                      {emp.is_active && (
                        <button
                          onClick={() => setDeactivateId(emp.id)}
                          className="text-xs text-th-text-muted hover:text-red-400 transition-colors"
                        >
                          Deactivate
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > perPage && (
        <div className="mt-4">
          <Pagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </div>
      )}

      {modalEmployee !== undefined && (
        <EmployeeModal
          employee={modalEmployee}
          onSave={handleSave}
          onClose={() => setModalEmployee(undefined)}
        />
      )}

      <ConfirmDialog
        isOpen={deactivateId !== null}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivateId(null)}
        title="Deactivate Employee"
        message="This will deactivate the employee. They will no longer be able to log in."
        confirmLabel="Deactivate"
        variant="danger"
      />
    </div>
  )
}
