import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calculator, Copy, Trash2 } from 'lucide-react'
import { createEstimate, deleteEstimate, duplicateEstimate } from '../api/estimates'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from './ConfirmDialog'

const formatCurrency = (value) => {
  if (!value && value !== 0) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

export default function JobEstimatesTab({ jobId, estimates, onRefresh }) {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [showModal, setShowModal] = useState(false)
  const [name, setName] = useState('')
  const [taxRate, setTaxRate] = useState('7.00')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleteId, setDeleteId] = useState(null)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) {
      setFormError('Name is required')
      return
    }
    setSaving(true)
    setFormError('')
    try {
      const est = await createEstimate({
        job_id: jobId,
        name: name.trim(),
        tax_rate: (parseFloat(taxRate) / 100).toFixed(4),
      })
      setShowModal(false)
      setName('')
      setTaxRate('7.00')
      addToast('Estimate created')
      navigate(`/estimates/${est.id}`)
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create estimate')
    } finally {
      setSaving(false)
    }
  }

  const handleDuplicate = async (id) => {
    try {
      const est = await duplicateEstimate(id)
      addToast('Estimate duplicated')
      navigate(`/estimates/${est.id}`)
    } catch {
      addToast('Failed to duplicate estimate', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteEstimate(deleteId)
      setDeleteId(null)
      addToast('Estimate deleted')
      onRefresh()
    } catch {
      addToast('Failed to delete estimate', 'error')
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div />
        <button
          onClick={() => setShowModal(true)}
          className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
        >
          New Estimate
        </button>
      </div>

      {/* Estimate List */}
      {estimates.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-center">
          <Calculator size={24} className="text-th-text-muted mb-2" />
          <p className="text-th-text-muted text-sm">No estimates yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {estimates.map((est) => (
            <div
              key={est.id}
              className="flex items-center justify-between bg-surface-hover/50 rounded-lg px-4 py-3 hover:bg-surface-hover transition-colors cursor-pointer group"
              onClick={() => navigate(`/estimates/${est.id}`)}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-th-text truncate">
                  {est.name}
                </p>
                <p className="text-xs text-th-text-muted mt-0.5">
                  {est.line_items?.length || 0} items
                  {est.created_at && (
                    <> &middot; {new Date(est.created_at).toLocaleDateString()}</>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-brand-purple font-semibold">
                  {formatCurrency(est.total)}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDuplicate(est.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-th-text transition-all"
                  title="Duplicate"
                >
                  <Copy size={14} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setDeleteId(est.id)
                  }}
                  className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold text-th-text mb-4">
              New Estimate
            </h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Roof Estimate - IKO Cambridge"
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
                  Tax Rate (%)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={taxRate}
                  onChange={(e) => setTaxRate(e.target.value)}
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text font-mono focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                />
              </div>
              {formError && (
                <p className="text-red-400 text-sm">{formError}</p>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false)
                    setFormError('')
                  }}
                  className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                >
                  {saving ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Delete Estimate"
        message="This will permanently delete this estimate and all its line items."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
