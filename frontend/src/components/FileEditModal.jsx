import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

export default function FileEditModal({
  doc,
  availableFolders = [],
  onClose,
  onSave,
}) {
  const [folder, setFolder] = useState('General')
  const [description, setDescription] = useState('')
  const [showInWorkOrder, setShowInWorkOrder] = useState(false)
  const [showInEstimate, setShowInEstimate] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (doc) {
      setFolder(doc.folder || 'General')
      setDescription(doc.description || '')
      setShowInWorkOrder(!!doc.show_in_work_order)
      setShowInEstimate(!!doc.show_in_estimate)
    }
  }, [doc])

  if (!doc) return null

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await onSave({
        folder,
        description,
        showInWorkOrder,
        showInEstimate,
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-th-text truncate pr-4">
            {doc.original_filename}
          </h3>
          <button
            onClick={onClose}
            className="text-th-text-muted hover:text-th-text shrink-0"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs text-th-text-secondary font-medium block mb-1">
              Folder
            </label>
            <select
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-th-border-secondary text-th-text"
            >
              {availableFolders.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-th-text-secondary font-medium block mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Add a caption…"
              className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-th-border-secondary text-th-text resize-none"
            />
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-th-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={showInWorkOrder}
                onChange={(e) => setShowInWorkOrder(e.target.checked)}
                className="rounded"
              />
              Show in work order
            </label>
            <label className="flex items-center gap-2 text-sm text-th-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={showInEstimate}
                onChange={(e) => setShowInEstimate(e.target.checked)}
                className="rounded"
              />
              Show in estimate
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm rounded-lg bg-btn-primary-bg text-btn-primary-text hover:bg-btn-primary-hover disabled:opacity-50"
            >
              {submitting ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
