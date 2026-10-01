import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Camera,
  Download,
  Edit2,
  Eye,
  FileCode,
  FileText,
  Folder,
  Grid,
  Image as ImageIcon,
  List,
  Plus,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import {
  deleteFile,
  downloadFile,
  fetchFileBlobUrl,
  listFiles,
  listFolders,
  updateFile,
  uploadFiles,
} from '../api/documents'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from './ConfirmDialog'
import FileUploadModal from './FileUploadModal'
import FileEditModal from './FileEditModal'

export const DEFAULT_FOLDERS = [
  'General',
  'Contracts',
  'Estimates',
  'Insurance Documents',
  'Job Paperwork',
  'Roof Report',
  'Photos',
]

const FILE_ICONS = {
  'application/pdf': FileText,
  'text/xml': FileCode,
  'application/xml': FileCode,
}

function iconFor(contentType) {
  if (contentType?.startsWith('image/')) return ImageIcon
  return FILE_ICONS[contentType] || FileText
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function useAuthedBlobUrl(docId, enabled = true) {
  const [url, setUrl] = useState(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    if (!enabled || !docId) return undefined
    let cancelled = false
    let createdUrl = null
    setUrl(null)
    setError(false)
    fetchFileBlobUrl(docId)
      .then((blobUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(blobUrl)
          return
        }
        createdUrl = blobUrl
        setUrl(blobUrl)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [docId, enabled])
  return { url, error }
}

function PhotoThumbnail({ doc }) {
  const { url, error } = useAuthedBlobUrl(doc.id)
  if (error || !url) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-hover">
        <ImageIcon size={28} className="text-th-text-muted" />
      </div>
    )
  }
  return (
    <img
      src={url}
      alt={doc.description || doc.original_filename}
      className="w-full h-full object-cover"
    />
  )
}

function PhotoLightbox({ doc, onClose }) {
  const { url, error } = useAuthedBlobUrl(doc?.id, !!doc)
  if (!doc) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-6">
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-white p-2 hover:bg-white/10 rounded-lg"
        aria-label="Close"
      >
        <X size={28} />
      </button>
      <div className="max-w-5xl max-h-full flex flex-col items-center gap-3">
        {url ? (
          <img
            src={url}
            alt={doc.original_filename}
            className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-2xl"
          />
        ) : error ? (
          <div className="text-white">Failed to load image</div>
        ) : (
          <div className="text-white">Loading…</div>
        )}
        <div className="text-white text-center max-w-2xl">
          <p className="text-sm font-medium">{doc.original_filename}</p>
          {doc.description && (
            <p className="text-xs text-white/70 mt-1">{doc.description}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function FilesTab({ entityType, entityId, onCountChange }) {
  const { addToast } = useToast()
  const [files, setFiles] = useState([])
  const [folders, setFolders] = useState([])
  const [activeFolder, setActiveFolder] = useState(null) // null = all
  const [view, setView] = useState('grid')
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [editDoc, setEditDoc] = useState(null)
  const [deleteId, setDeleteId] = useState(null)
  const [lightbox, setLightbox] = useState(null)
  const [customFolderName, setCustomFolderName] = useState('')
  const [showNewFolder, setShowNewFolder] = useState(false)
  const fileInputRef = useRef(null)

  const load = async () => {
    setLoading(true)
    try {
      const [fileData, folderData] = await Promise.all([
        listFiles(entityType, entityId),
        listFolders(entityType, entityId),
      ])
      setFiles(fileData.items || [])
      setFolders(folderData.items || [])
      onCountChange?.(fileData.total || 0)
    } catch (err) {
      addToast('Failed to load files', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId])

  const displayedFolders = useMemo(() => {
    const seen = new Set(folders.map((f) => f.name))
    const merged = [...folders]
    DEFAULT_FOLDERS.forEach((name) => {
      if (!seen.has(name)) {
        merged.push({ name, file_count: 0, photo_count: 0 })
      }
    })
    return merged.sort((a, b) => a.name.localeCompare(b.name))
  }, [folders])

  const filteredFiles = useMemo(() => {
    if (!activeFolder) return files
    return files.filter((f) => f.folder === activeFolder)
  }, [files, activeFolder])

  const isPhotoFolder = activeFolder === 'Photos'

  const handleUpload = async (selectedFiles, options) => {
    if (!selectedFiles || !selectedFiles.length) return
    try {
      await uploadFiles(entityType, entityId, Array.from(selectedFiles), options)
      addToast(`${selectedFiles.length} file(s) uploaded`)
      setShowUpload(false)
      load()
    } catch (err) {
      addToast(err.response?.data?.detail || 'Upload failed', 'error')
    }
  }

  const handleQuickUpload = (e) => {
    const incoming = Array.from(e.target.files)
    if (!incoming.length) return
    handleUpload(incoming, {
      folder: activeFolder || 'General',
      showInWorkOrder: false,
      showInEstimate: false,
    })
    e.target.value = ''
  }

  const handleDownload = async (doc) => {
    try {
      await downloadFile(doc.id, doc.original_filename)
    } catch {
      addToast('Download failed', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteFile(deleteId)
      setDeleteId(null)
      addToast('File deleted')
      load()
    } catch {
      addToast('Delete failed', 'error')
    }
  }

  const handleSaveEdit = async (patch) => {
    if (!editDoc) return
    try {
      await updateFile(editDoc.id, patch)
      addToast('File updated')
      setEditDoc(null)
      load()
    } catch {
      addToast('Update failed', 'error')
    }
  }

  const handleCreateFolder = (e) => {
    e.preventDefault()
    const name = customFolderName.trim()
    if (!name) return
    setActiveFolder(name)
    setShowNewFolder(false)
    setCustomFolderName('')
    // Folder will materialize once the first file is uploaded to it.
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Folder sidebar */}
      <aside className="lg:w-56 shrink-0">
        <div className="space-y-1">
          <button
            onClick={() => setActiveFolder(null)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-colors ${
              activeFolder === null
                ? 'bg-btn-primary-bg/10 text-th-text font-medium'
                : 'text-th-text-secondary hover:bg-surface-hover'
            }`}
          >
            <span className="flex items-center gap-2">
              <Folder size={14} />
              All Files
            </span>
            <span className="text-xs text-th-text-muted">{files.length}</span>
          </button>
          {displayedFolders.map((f) => {
            const Icon = f.name === 'Photos' ? Camera : Folder
            const active = activeFolder === f.name
            return (
              <button
                key={f.name}
                onClick={() => setActiveFolder(f.name)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-colors ${
                  active
                    ? 'bg-btn-primary-bg/10 text-th-text font-medium'
                    : 'text-th-text-secondary hover:bg-surface-hover'
                }`}
              >
                <span className="flex items-center gap-2 truncate">
                  <Icon size={14} className="shrink-0" />
                  <span className="truncate">{f.name}</span>
                </span>
                {f.file_count > 0 && (
                  <span className="text-xs text-th-text-muted">{f.file_count}</span>
                )}
              </button>
            )
          })}
          {showNewFolder ? (
            <form
              onSubmit={handleCreateFolder}
              className="flex gap-1 px-1 pt-1"
            >
              <input
                autoFocus
                value={customFolderName}
                onChange={(e) => setCustomFolderName(e.target.value)}
                placeholder="Folder name"
                className="flex-1 px-2 py-1.5 text-xs rounded bg-surface border border-th-border-secondary text-th-text"
              />
              <button
                type="submit"
                className="px-2 py-1 text-xs bg-btn-primary-bg text-btn-primary-text rounded"
              >
                Add
              </button>
            </form>
          ) : (
            <button
              onClick={() => setShowNewFolder(true)}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-th-text-muted hover:bg-surface-hover transition-colors flex items-center gap-2"
            >
              <Plus size={14} />
              New Folder
            </button>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 min-w-0">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-4 gap-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-th-text">
              {activeFolder || 'All Files'}
            </h3>
            <span className="text-xs text-th-text-muted">
              {filteredFiles.length} file{filteredFiles.length === 1 ? '' : 's'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-th-border-secondary overflow-hidden">
              <button
                onClick={() => setView('grid')}
                className={`px-2 py-1.5 text-xs ${
                  view === 'grid'
                    ? 'bg-btn-primary-bg/10 text-th-text'
                    : 'text-th-text-muted hover:bg-surface-hover'
                }`}
                title="Grid view"
              >
                <Grid size={14} />
              </button>
              <button
                onClick={() => setView('list')}
                className={`px-2 py-1.5 text-xs ${
                  view === 'list'
                    ? 'bg-btn-primary-bg/10 text-th-text'
                    : 'text-th-text-muted hover:bg-surface-hover'
                }`}
                title="List view"
              >
                <List size={14} />
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.heic,.heif,.webp,.gif,.xml"
              onChange={handleQuickUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-1.5 text-xs rounded-lg border border-th-border-secondary text-th-text-secondary hover:bg-surface-hover flex items-center gap-1.5"
            >
              <Upload size={14} />
              Quick Upload
            </button>
            <button
              onClick={() => setShowUpload(true)}
              className="px-3 py-1.5 text-xs rounded-lg bg-btn-primary-bg text-btn-primary-text hover:bg-btn-primary-hover flex items-center gap-1.5"
            >
              <Plus size={14} />
              Upload
            </button>
          </div>
        </div>

        {/* File grid/list */}
        {loading ? (
          <div className="text-th-text-muted text-sm py-10 text-center">
            Loading files…
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="border-2 border-dashed border-th-border-secondary rounded-xl py-12 text-center">
            <Upload size={28} className="mx-auto text-th-text-muted mb-2" />
            <p className="text-sm text-th-text-secondary">
              No files in {activeFolder || 'this folder'} yet
            </p>
            <p className="text-xs text-th-text-muted mt-1">
              Click "Upload" to add files
            </p>
          </div>
        ) : view === 'grid' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {filteredFiles.map((doc) => (
              <FileGridCard
                key={doc.id}
                doc={doc}
                isPhotoFolder={isPhotoFolder}
                onPreview={() => doc.is_photo && setLightbox(doc)}
                onDownload={() => handleDownload(doc)}
                onEdit={() => setEditDoc(doc)}
                onDelete={() => setDeleteId(doc.id)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            {filteredFiles.map((doc) => (
              <FileListRow
                key={doc.id}
                doc={doc}
                onDownload={() => handleDownload(doc)}
                onEdit={() => setEditDoc(doc)}
                onDelete={() => setDeleteId(doc.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      <FileUploadModal
        isOpen={showUpload}
        defaultFolder={activeFolder || 'General'}
        availableFolders={displayedFolders.map((f) => f.name)}
        onClose={() => setShowUpload(false)}
        onUpload={handleUpload}
      />
      <FileEditModal
        doc={editDoc}
        availableFolders={displayedFolders.map((f) => f.name)}
        onClose={() => setEditDoc(null)}
        onSave={handleSaveEdit}
      />
      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Delete File"
        message="This will permanently delete this file."
        confirmLabel="Delete"
        variant="danger"
      />
      <PhotoLightbox doc={lightbox} onClose={() => setLightbox(null)} />
    </div>
  )
}

function FileGridCard({ doc, isPhotoFolder, onPreview, onDownload, onEdit, onDelete }) {
  const Icon = iconFor(doc.content_type)
  const isImage = doc.is_photo
  return (
    <div className="rounded-xl border border-th-border-secondary overflow-hidden group bg-surface hover:border-th-border transition-colors">
      <div
        className="aspect-square bg-surface-hover relative cursor-pointer"
        onClick={isImage ? onPreview : onDownload}
        title={isImage ? 'Preview' : 'Download'}
      >
        {isImage ? (
          <PhotoThumbnail doc={doc} />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Icon size={36} className="text-th-text-muted" />
          </div>
        )}
        {(doc.show_in_work_order || doc.show_in_estimate) && (
          <div className="absolute top-1.5 left-1.5 flex gap-1">
            {doc.show_in_work_order && (
              <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/90 text-black rounded">
                WO
              </span>
            )}
            {doc.show_in_estimate && (
              <span className="text-[10px] px-1.5 py-0.5 bg-brand-purple/90 text-white rounded">
                EST
              </span>
            )}
          </div>
        )}
        <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 flex gap-1 transition-opacity">
          {isImage && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onPreview()
              }}
              className="p-1 bg-black/50 text-white rounded hover:bg-black/70"
              title="Preview"
            >
              <Eye size={12} />
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDownload()
            }}
            className="p-1 bg-black/50 text-white rounded hover:bg-black/70"
            title="Download"
          >
            <Download size={12} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit()
            }}
            className="p-1 bg-black/50 text-white rounded hover:bg-black/70"
            title="Edit"
          >
            <Edit2 size={12} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="p-1 bg-red-600/80 text-white rounded hover:bg-red-700"
            title="Delete"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
      <div className="p-2">
        <p className="text-xs text-th-text truncate" title={doc.original_filename}>
          {doc.original_filename}
        </p>
        <p className="text-[10px] text-th-text-muted mt-0.5 flex items-center justify-between">
          <span>{formatFileSize(doc.file_size)}</span>
          {!isPhotoFolder && doc.folder && (
            <span className="truncate ml-2">{doc.folder}</span>
          )}
        </p>
        {doc.description && (
          <p className="text-[10px] text-th-text-muted mt-1 line-clamp-2">
            {doc.description}
          </p>
        )}
      </div>
    </div>
  )
}

function FileListRow({ doc, onDownload, onEdit, onDelete }) {
  const Icon = iconFor(doc.content_type)
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg group hover:bg-surface-hover/50 transition-colors">
      <Icon size={18} className="text-th-text-muted shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <button
            onClick={onDownload}
            className="text-sm text-th-text truncate hover:text-brand-purple transition-colors"
          >
            {doc.original_filename}
          </button>
          {doc.show_in_work_order && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/80 text-black rounded">
              WO
            </span>
          )}
          {doc.show_in_estimate && (
            <span className="text-[10px] px-1.5 py-0.5 bg-brand-purple/80 text-white rounded">
              EST
            </span>
          )}
        </div>
        <p className="text-xs text-th-text-muted">
          {doc.folder && <span>{doc.folder} &middot; </span>}
          {formatFileSize(doc.file_size)}
          {doc.created_at && (
            <> &middot; {new Date(doc.created_at).toLocaleDateString()}</>
          )}
          {doc.uploader_name && <> &middot; {doc.uploader_name}</>}
        </p>
        {doc.description && (
          <p className="text-xs text-th-text-muted mt-0.5 truncate">
            {doc.description}
          </p>
        )}
      </div>
      <button
        onClick={onDownload}
        className="text-th-text-muted hover:text-brand-purple transition-colors"
        title="Download"
      >
        <Download size={14} />
      </button>
      <button
        onClick={onEdit}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-th-text transition-all"
        title="Edit"
      >
        <Edit2 size={14} />
      </button>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all"
        title="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
