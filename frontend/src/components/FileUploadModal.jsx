import { useEffect, useRef, useState } from 'react'
import { Upload, X } from 'lucide-react'

export default function FileUploadModal({
  isOpen,
  defaultFolder = 'General',
  availableFolders = [],
  onClose,
  onUpload,
}) {
  const [files, setFiles] = useState([])
  const [folder, setFolder] = useState(defaultFolder)
  const [description, setDescription] = useState('')
  const [showInWorkOrder, setShowInWorkOrder] = useState(false)
  const [showInEstimate, setShowInEstimate] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setFiles([])
      setFolder(defaultFolder)
      setDescription('')
      setShowInWorkOrder(false)
      setShowInEstimate(false)
    }
  }, [isOpen, defaultFolder])

  if (!isOpen) return null

  const submit = async (e) => {
    e?.preventDefault?.()
    if (!files.length) return
    setSubmitting(true)
    try {
      await onUpload(files, {
        folder,
        description: description || null,
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
      <div className="relative bg-surface rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-th-text">Upload Files</h3>
          <button
            onClick={onClose}
            className="text-th-text-muted hover:text-th-text"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              setFiles(Array.from(e.dataTransfer.files))
            }}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
              dragOver
                ? 'border-brand-purple bg-btn-primary-bg/5'
                : 'border-th-border-secondary hover:border-th-border'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.heic,.heif,.webp,.gif,.xml"
              onChange={(e) => setFiles(Array.from(e.target.files))}
              className="hidden"
            />
            <Upload size={24} className="mx-auto text-th-text-muted mb-2" />
            {files.length === 0 ? (
              <>
                <p className="text-sm text-th-text-secondary">
                  Drop files here or click to select
                </p>
                <p className="text-xs text-th-text-muted mt-1">
                  PDF, PNG, JPG, HEIC, WEBP, XML — Max 20 MB
                </p>
              </>
            ) : (
              <div className="text-left text-sm text-th-text">
                <p className="font-medium mb-1">
                  {files.length} file{files.length === 1 ? '' : 's'} selected
                </p>
                <ul className="text-xs text-th-text-muted space-y-0.5 max-h-24 overflow-y-auto">
                  {files.map((f, i) => (
                    <li key={i} className="truncate">{f.name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

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
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="e.g. Front elevation, post-install"
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
              disabled={!files.length || submitting}
              className="px-4 py-2 text-sm rounded-lg bg-btn-primary-bg text-btn-primary-text hover:bg-btn-primary-hover disabled:opacity-50"
            >
              {submitting ? 'Uploading…' : `Upload ${files.length || ''}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
