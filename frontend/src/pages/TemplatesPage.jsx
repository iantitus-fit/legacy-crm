import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Plus, Copy, Trash2, Pencil } from 'lucide-react'
import { listTemplates, createTemplate, duplicateTemplate, deleteTemplate } from '../api/estimateTemplates'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteId, setDeleteId] = useState(null)
  const navigate = useNavigate()
  const { addToast } = useToast()

  const fetchTemplates = async () => {
    try {
      const data = await listTemplates()
      setTemplates(data.items)
    } catch {
      addToast('Failed to load templates', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
  }, [])

  const handleCreate = async () => {
    try {
      const t = await createTemplate({ name: 'New Template' })
      navigate(`/templates/${t.id}`)
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to create template', 'error')
    }
  }

  const handleDuplicate = async (id) => {
    try {
      const t = await duplicateTemplate(id)
      addToast('Template duplicated')
      navigate(`/templates/${t.id}`)
    } catch {
      addToast('Failed to duplicate', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTemplate(deleteId)
      setDeleteId(null)
      fetchTemplates()
      addToast('Template deactivated')
    } catch {
      addToast('Failed to delete', 'error')
    }
  }

  if (loading) return <LoadingSpinner centered />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-th-text">Estimate Templates</h1>
          <p className="text-sm text-th-text-muted mt-1">
            {templates.length} template{templates.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded-lg px-4 py-2.5 text-sm transition-colors"
        >
          <Plus size={16} />
          New Template
        </button>
      </div>

      {templates.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No templates yet"
          description="Create a template to speed up estimate generation"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <div
              key={t.id}
              className="bg-surface rounded-xl border border-th-border p-5 hover:border-th-border-secondary transition-colors group"
            >
              <div className="flex items-start justify-between mb-3">
                <div
                  className="cursor-pointer flex-1 min-w-0"
                  onClick={() => navigate(`/templates/${t.id}`)}
                >
                  <h3 className="text-base font-semibold text-th-text truncate group-hover:text-brand-purple transition-colors">
                    {t.name}
                  </h3>
                  {t.description && (
                    <p className="text-xs text-th-text-muted mt-1 truncate">{t.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 ml-2 shrink-0">
                  <button
                    onClick={() => navigate(`/templates/${t.id}`)}
                    className="p-1.5 text-th-text-muted hover:text-brand-purple-text transition-colors"
                    title="Edit"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    onClick={() => handleDuplicate(t.id)}
                    className="p-1.5 text-th-text-muted hover:text-blue-400 transition-colors"
                    title="Duplicate"
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => setDeleteId(t.id)}
                    className="p-1.5 text-th-text-muted hover:text-red-400 transition-colors"
                    title="Deactivate"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs text-th-text-muted">
                <span>{t.item_count} item{t.item_count !== 1 ? 's' : ''}</span>
                <span className="font-mono">{parseFloat(t.default_margin_pct)}% margin</span>
                <span className="font-mono">{parseFloat(t.default_waste_pct)}% waste</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Deactivate Template"
        message="This template will be hidden from the list. Are you sure?"
        confirmLabel="Deactivate"
        variant="danger"
      />
    </div>
  )
}
