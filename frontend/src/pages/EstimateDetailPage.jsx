import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Briefcase,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Eye,
  FileText,
  Mail,
  MessageCircle,
  FolderPlus,
  GripVertical,
  Loader2,
  Package,
  Pencil,
  Plus,
  Receipt,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import ReactQuill from 'react-quill-new'
import 'react-quill-new/dist/quill.snow.css'
import {
  getEstimate,
  updateEstimate,
  duplicateEstimate,
  approveEstimateInternal,
  addLineItem,
  updateLineItem,
  deleteLineItem,
  duplicateLineItem,
  reorderLineItems,
  createSection,
  updateSection,
  deleteSection,
} from '../api/estimates'
import {
  createChangeOrder,
  updateChangeOrder,
  deleteChangeOrder as deleteChangeOrderApi,
  addChangeOrderItem,
  updateChangeOrderItem,
  deleteChangeOrderItem,
  duplicateChangeOrderItem,
  sendChangeOrder,
} from '../api/changeOrders'
import AddItemSplitButton from '../components/AddItemSplitButton'
import MaterialPickerModal from '../components/MaterialPickerModal'
import BackButton from '../components/BackButton'
import PhoneLink from '../components/PhoneLink'
import AddressLink from '../components/AddressLink'
import { listTemplates, previewTemplate, applyTemplate } from '../api/estimateTemplates'
import { createInvoice, createDepositInvoice } from '../api/invoices'
import { listCrews } from '../api/crews'
import { listEmployees } from '../api/employees'
import { sendEstimateViaSms } from '../api/sms'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'
import NotesTab from '../components/NotesTab'
import FilesTab from '../components/FilesTab'
import WorkOrderDropdown from '../components/WorkOrderDropdown'
import WorkOrderSendModal from '../components/WorkOrderSendModal'
import AIPanelButton from '../components/AIPanelButton'

const STATUS_BADGES = {
  draft: { label: 'Draft', bg: 'bg-gray-500/20', text: 'text-gray-400' },
  sent: { label: 'Sent', bg: 'bg-blue-500/20', text: 'text-blue-400' },
  viewed: { label: 'Viewed', bg: 'bg-blue-400/20', text: 'text-blue-300' },
  approved: { label: 'Approved', bg: 'bg-green-500/20', text: 'text-green-400' },
  rejected: { label: 'Rejected', bg: 'bg-red-500/20', text: 'text-red-400' },
  changes_requested: { label: 'Changes Requested', bg: 'bg-amber-500/20', text: 'text-amber-400' },
}

function EstimateStatusBadge({ status }) {
  const badge = STATUS_BADGES[status] || STATUS_BADGES.draft
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
      {badge.label}
    </span>
  )
}

const formatCurrency = (value) => {
  if (!value && value !== 0) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

const quillModules = {
  toolbar: [
    [{ size: ['small', false, 'large', 'huge'] }],
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    [{ background: [] }],
    ['clean'],
  ],
}

const quillFormats = ['size', 'bold', 'italic', 'underline', 'list', 'background']

function stripHtml(html) {
  if (!html) return ''
  const tmp = document.createElement('div')
  tmp.innerHTML = html
  return tmp.textContent || tmp.innerText || ''
}

function LineItemEditModal({ open, item, sections, onSave, onClose }) {
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')
  const [qty, setQty] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [notes, setNotes] = useState('')
  const [sectionId, setSectionId] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (item && open) {
      setDescription(item.description || '')
      setBody(item.body || '')
      setQty(item.qty ?? '')
      setUnitPrice(item.unit_price ?? '')
      setNotes(item.notes || '')
      setSectionId(item.section_id ?? '')
    }
  }, [item, open])

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(item.id, {
        description,
        body: body || null,
        qty: parseFloat(qty) || 0,
        unit_price: parseFloat(unitPrice) || 0,
        notes: notes || null,
        section_id: sectionId === '' ? null : Number(sectionId),
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  if (!open || !item) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">Edit Line Item</h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 space-y-4">
          {/* Item Name */}
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Item Name</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </div>

          {/* Rich Text Description */}
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Description</label>
            <div className="quill-dark">
              <ReactQuill
                theme="snow"
                value={body}
                onChange={setBody}
                modules={quillModules}
                formats={quillFormats}
                placeholder="Add detailed description..."
              />
            </div>
          </div>

          {/* Qty + Price row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Quantity</label>
              <input
                type="number"
                step="0.01"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Unit Price</label>
              <input
                type="number"
                step="0.01"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>

          {/* Section */}
          {sections && sections.length > 0 && (
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Section</label>
              <select
                value={sectionId}
                onChange={(e) => setSectionId(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">No section (unsectioned)</option>
                {sections.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Notes (internal)</label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. only for valleys, 1 box for 63 sheets"
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text-secondary focus:outline-none focus:border-th-border-focus resize-y"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SectionEditModal({ open, section, onSave, onClose }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setName(section?.name || '')
      setDescription(section?.description || '')
    }
  }, [section, open])

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await onSave({ name: name.trim(), description: description || null })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">
            {section ? 'Edit Section' : 'Add Section'}
          </h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text">
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Section Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Roofing Materials"
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs text-th-text-muted mb-1">Description (optional)</label>
            <div className="quill-dark">
              <ReactQuill
                theme="snow"
                value={description}
                onChange={setDescription}
                modules={quillModules}
                formats={quillFormats}
                placeholder="Section description..."
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
          >
            {saving ? 'Saving...' : section ? 'Save' : 'Add Section'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SortableRow({ item, onEdit, onDelete, onDuplicate, showQty, showPrice, showTotal }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const bodyPreview = stripHtml(item.body)

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-3 py-2 group hover:bg-surface-hover/30 transition-colors"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-th-text-muted hover:text-th-text shrink-0 touch-none"
      >
        <GripVertical size={14} />
      </button>

      {/* Description + Body preview */}
      <div
        className="flex-1 min-w-0 cursor-pointer"
        onClick={() => onEdit(item)}
      >
        <span className="text-sm text-th-text block truncate">
          {item.description || 'Untitled item'}
        </span>
        {bodyPreview ? (
          <span className="text-xs text-th-text-muted block truncate mt-0.5">
            {bodyPreview}
          </span>
        ) : (
          <span className="text-xs text-th-text-muted block mt-0.5 hover:text-th-text transition-colors">
            Add description...
          </span>
        )}
      </div>

      {/* Edit button */}
      <button
        onClick={() => onEdit(item)}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-brand-purple transition-all shrink-0 p-1"
        title="Edit item"
      >
        <Pencil size={13} />
      </button>

      {/* Duplicate button */}
      <button
        onClick={() => onDuplicate(item.id)}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-brand-purple transition-all shrink-0 p-1"
        title="Duplicate item"
      >
        <Copy size={13} />
      </button>

      {/* Qty */}
      {showQty && (
        <div className="w-12 sm:w-16 shrink-0 text-right">
          <span className="text-sm font-mono text-th-text">
            {parseFloat(item.qty)}
          </span>
        </div>
      )}

      {/* Unit Price */}
      {showPrice && (
        <div className="w-20 sm:w-24 shrink-0 text-right">
          <span className="text-sm font-mono text-th-text">
            {formatCurrency(item.unit_price)}
          </span>
        </div>
      )}

      {/* Line Total */}
      {showTotal && (
        <div className="w-20 sm:w-24 shrink-0 text-right">
          <span className="text-sm font-mono text-th-text">
            {formatCurrency(item.line_total)}
          </span>
        </div>
      )}

      {/* Delete */}
      <button
        onClick={() => onDelete(item.id)}
        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all shrink-0"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

function SectionHeader({ section, onEdit, onDelete, onAddItem, onAddFromMaterials, showTotal, collapsed, onToggle }) {
  const descPreview = stripHtml(section.description)

  return (
    <div className="flex items-center gap-2 px-3 py-2.5 bg-surface-hover/40 border-b border-th-border">
      <button
        onClick={onToggle}
        className="text-th-text-muted hover:text-th-text shrink-0"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
      </button>
      <div className="flex-1 min-w-0">
        <span className="text-sm font-semibold text-th-text">{section.name}</span>
        {descPreview && (
          <span className="text-xs text-th-text-muted block truncate mt-0.5">{descPreview}</span>
        )}
      </div>
      <button
        onClick={onAddItem}
        className="text-th-text-muted hover:text-brand-purple transition-colors p-1"
        title="Add blank item to section"
      >
        <Plus size={14} />
      </button>
      <button
        onClick={onAddFromMaterials}
        className="text-th-text-muted hover:text-brand-purple transition-colors p-1"
        title="Add item from materials"
      >
        <Package size={14} />
      </button>
      <button
        onClick={onEdit}
        className="text-th-text-muted hover:text-brand-purple transition-colors p-1"
        title="Edit section"
      >
        <Pencil size={13} />
      </button>
      <button
        onClick={onDelete}
        className="text-th-text-muted hover:text-red-400 transition-colors p-1"
        title="Delete section"
      >
        <Trash2 size={14} />
      </button>
      {showTotal && (
        <div className="w-20 sm:w-24 shrink-0 text-right">
          <span className="text-xs font-mono text-th-text-secondary">
            {formatCurrency(section.subtotal)}
          </span>
        </div>
      )}
    </div>
  )
}

function ApplyTemplateModal({ open, onClose, estimateId, onApplied }) {
  const [templates, setTemplates] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [measurements, setMeasurements] = useState({
    total_area: '',
    ridge: '',
    hip: '',
    valley: '',
    eave: '',
    rake: '',
  })
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    if (!open) return
    listTemplates().then((d) => setTemplates(d.items)).catch(() => {})
    setSelectedId('')
    setMeasurements({ total_area: '', ridge: '', hip: '', valley: '', eave: '', rake: '' })
    setPreview(null)
  }, [open])

  const handlePreview = async () => {
    if (!selectedId) return
    setLoading(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      const data = await previewTemplate(selectedId, { measurements: m })
      setPreview(data)
    } catch {
      addToast('Failed to generate preview', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    if (!selectedId) return
    setApplying(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      await applyTemplate(estimateId, selectedId, m)
      addToast('Template applied successfully')
      onApplied()
      onClose()
    } catch {
      addToast('Failed to apply template', 'error')
    } finally {
      setApplying(false)
    }
  }

  if (!open) return null

  const measurementFields = [
    { key: 'total_area', label: 'Total Area', unit: 'squares' },
    { key: 'ridge', label: 'Ridge Length', unit: 'LF' },
    { key: 'hip', label: 'Hip Length', unit: 'LF' },
    { key: 'valley', label: 'Valley Length', unit: 'LF' },
    { key: 'eave', label: 'Eave Length', unit: 'LF' },
    { key: 'rake', label: 'Rake Length', unit: 'LF' },
  ]

  const selectedTemplate = templates.find((t) => t.id === Number(selectedId))
  const usedTypes = new Set(
    (selectedTemplate?.items || [])
      .map((i) => i.measurement_type)
      .filter(Boolean)
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text flex items-center gap-2">
            <FileText size={20} className="text-brand-purple" />
            Apply Template
          </h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text"><X size={20} /></button>
        </div>

        <div className="mb-4">
          <label className="block text-xs text-th-text-muted mb-1">Template</label>
          <select
            value={selectedId}
            onChange={(e) => { setSelectedId(e.target.value); setPreview(null) }}
            className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
          >
            <option value="">Select a template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name} ({t.item_count} items)</option>
            ))}
          </select>
        </div>

        {selectedId && (
          <div className="mb-4">
            <label className="block text-xs text-th-text-muted mb-2">Roof Measurements</label>
            <div className="grid grid-cols-3 gap-3">
              {measurementFields.map(({ key, label, unit }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs text-th-text-secondary">{label}</span>
                    {usedTypes.has(key) && (
                      <span className="text-[10px] text-brand-purple font-medium">REQUIRED</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="0.1"
                      value={measurements[key]}
                      onChange={(e) => setMeasurements((m) => ({ ...m, [key]: e.target.value }))}
                      className="flex-1 bg-page border border-th-border rounded px-2 py-1.5 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
                      placeholder="0"
                    />
                    <span className="text-xs text-th-text-muted w-10">{unit}</span>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={handlePreview}
              disabled={loading}
              className="mt-3 px-4 py-2 bg-surface-hover hover:bg-th-border-secondary text-th-text text-sm rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? 'Calculating...' : 'Preview'}
            </button>
          </div>
        )}

        {preview && (
          <div className="flex-1 overflow-y-auto min-h-0 mb-4">
            <div className="bg-page rounded-lg border border-th-border overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-th-border">
                    <th className="text-left text-xs font-medium text-th-text-muted uppercase px-3 py-2">Description</th>
                    <th className="text-left text-xs font-medium text-th-text-muted uppercase px-3 py-2">Category</th>
                    <th className="text-right text-xs font-medium text-th-text-muted uppercase px-3 py-2">Qty</th>
                    <th className="text-right text-xs font-medium text-th-text-muted uppercase px-3 py-2">Unit Price</th>
                    <th className="text-right text-xs font-medium text-th-text-muted uppercase px-3 py-2">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-th-border/50">
                  {preview.items.map((item, idx) => (
                    <tr key={idx}>
                      <td className="px-3 py-2 text-sm text-th-text">{item.description}</td>
                      <td className="px-3 py-2 text-sm text-th-text-secondary">{item.category}</td>
                      <td className="px-3 py-2 text-sm font-mono text-th-text text-right">
                        {item.qty} {item.uom || ''}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-th-text text-right">
                        {formatCurrency(item.unit_price)}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-th-text text-right">
                        {formatCurrency(item.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex justify-between items-center px-3 py-2.5 border-t border-th-border bg-surface/50">
                <span className="text-sm text-th-text-secondary">{preview.item_count} items</span>
                <span className="text-base font-mono font-bold text-brand-purple">
                  {formatCurrency(preview.subtotal)}
                </span>
              </div>
            </div>
          </div>
        )}

        {preview && (
          <button
            onClick={handleApply}
            disabled={applying}
            className="w-full bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text font-semibold rounded-lg py-2.5 transition-colors"
          >
            {applying ? 'Applying...' : `Apply ${preview.item_count} Items to Estimate`}
          </button>
        )}
      </div>
    </div>
  )
}

function MiniToggle({ checked, onChange, label, title }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      title={title}
      onClick={() => onChange(!checked)}
      className="flex items-center gap-1 group"
    >
      <span className="text-[11px] text-th-text-muted group-hover:text-th-text transition-colors">
        {label}
      </span>
      <span
        className={`relative inline-flex h-3.5 w-6 items-center rounded-full transition-colors ${
          checked ? 'bg-btn-primary-bg' : 'bg-th-border-secondary'
        }`}
      >
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full bg-white transition-transform ${
            checked ? 'translate-x-[11px]' : 'translate-x-[2px]'
          }`}
        />
      </span>
    </button>
  )
}

export default function EstimateDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [estimate, setEstimate] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState('')
  const [editingTax, setEditingTax] = useState(false)
  const [taxValue, setTaxValue] = useState('')
  const [deleteItemId, setDeleteItemId] = useState(null)
  const [showApplyTemplate, setShowApplyTemplate] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [activeTab, setActiveTab] = useState('items')
  const [fileCount, setFileCount] = useState(0)
  const [woSend, setWoSend] = useState(null)

  // Section state
  const [sectionModal, setSectionModal] = useState({ open: false, section: null })
  const [deleteSectionId, setDeleteSectionId] = useState(null)
  const [collapsedSections, setCollapsedSections] = useState({})
  const [addItemSectionId, setAddItemSectionId] = useState(null)

  // Change order state
  const [editCOItem, setEditCOItem] = useState(null) // { coId, item }
  const [deleteCOItemTarget, setDeleteCOItemTarget] = useState(null) // { coId, itemId }
  const [deleteCOId, setDeleteCOId] = useState(null)
  const [editCOName, setEditCOName] = useState(null) // { coId, name }
  const [sendCOModal, setSendCOModal] = useState(null) // CO object or null
  const [sendCOLoading, setSendCOLoading] = useState(false)
  const [sendCOForm, setSendCOForm] = useState({ to_email: '', subject: '', message: '' })

  // Material picker state: null | { target: 'estimate', sectionId: number | null }
  //                        or  { target: 'co', coId: number }
  const [materialPicker, setMaterialPicker] = useState(null)

  // Sprint 15d — crew/employee lists for the Job Info panel dropdowns
  const [crewOptions, setCrewOptions] = useState([])
  const [employeeOptions, setEmployeeOptions] = useState([])

  // PDF / Customer View state
  const [pdfLoading, setPdfLoading] = useState(false)
  const [showCustomerView, setShowCustomerView] = useState(false)

  const [showSendModal, setShowSendModal] = useState(false)
  const [sendLoading, setSendLoading] = useState(false)
  const [sendForm, setSendForm] = useState({ to_email: '', subject: '', message: '' })

  // Sprint 17c — send estimate link via SMS
  const [showSmsConfirm, setShowSmsConfirm] = useState(false)
  const [smsSending, setSmsSending] = useState(false)

  const handleSendViaText = async () => {
    if (!estimate?.contact_id) return
    setSmsSending(true)
    try {
      await sendEstimateViaSms(estimate.contact_id, Number(id))
      addToast('Estimate link sent via text', 'success')
      setShowSmsConfirm(false)
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to send text'
      addToast(detail, 'error')
    } finally {
      setSmsSending(false)
    }
  }

  const fetchEstimate = useCallback(async () => {
    try {
      const data = await getEstimate(id)
      setEstimate(data)
      setNameValue(data.name)
      setTaxValue((parseFloat(data.tax_rate) * 100).toFixed(2))
    } catch {
      addToast('Failed to load estimate', 'error')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchEstimate()
  }, [fetchEstimate])

  // Sprint 15d — load crew and employee options once for the Job Info panel
  useEffect(() => {
    listCrews({ isActive: true, perPage: 100 })
      .then((data) => setCrewOptions(data.items || []))
      .catch(() => setCrewOptions([]))
    listEmployees({ isActive: true, perPage: 100 })
      .then((data) => setEmployeeOptions(data.items || []))
      .catch(() => setEmployeeOptions([]))
  }, [])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = async (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const items = estimate.line_items
    const oldIndex = items.findIndex((i) => i.id === active.id)
    const newIndex = items.findIndex((i) => i.id === over.id)
    const reordered = arrayMove(items, oldIndex, newIndex)

    setEstimate((prev) => ({ ...prev, line_items: reordered }))

    try {
      await reorderLineItems(id, reordered.map((i) => i.id))
    } catch {
      addToast('Failed to reorder', 'error')
      fetchEstimate()
    }
  }

  const handleNameSave = async () => {
    setEditingName(false)
    if (nameValue.trim() && nameValue.trim() !== estimate.name) {
      try {
        await updateEstimate(id, { name: nameValue.trim() })
        fetchEstimate()
      } catch {
        addToast('Failed to update name', 'error')
      }
    }
  }

  const handleTaxSave = async () => {
    setEditingTax(false)
    const rate = parseFloat(taxValue) / 100
    if (!isNaN(rate) && rate.toFixed(4) !== parseFloat(estimate.tax_rate).toFixed(4)) {
      try {
        await updateEstimate(id, { tax_rate: rate.toFixed(4) })
        fetchEstimate()
      } catch {
        addToast('Failed to update tax rate', 'error')
      }
    }
  }

  const handleItemSave = async (itemId, values) => {
    try {
      await updateLineItem(id, itemId, values)
      fetchEstimate()
    } catch {
      addToast('Failed to update item', 'error')
    }
  }

  const handleAddItem = async (sectionId = null) => {
    try {
      const payload = {
        description: 'New item',
        qty: '1',
        unit_price: '0.00',
      }
      if (sectionId) payload.section_id = sectionId
      await addLineItem(id, payload)
      fetchEstimate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const openMaterialPickerForEstimate = (sectionId = null) => {
    setMaterialPicker({ target: 'estimate', sectionId })
  }

  const openMaterialPickerForCO = (coId) => {
    setMaterialPicker({ target: 'co', coId })
  }

  const handleMaterialSelected = async (material) => {
    const picker = materialPicker
    setMaterialPicker(null)
    if (!picker) return
    try {
      if (picker.target === 'estimate') {
        const newItem = await addLineItem(id, {
          description: material.description || 'New item',
          qty: '1',
          unit_price: String(material.unit_price ?? '0.00'),
          section_id: picker.sectionId ?? null,
        })
        await fetchEstimate()
        addToast('Item added from materials')
        // Open the edit modal so user can adjust qty/price before moving on
        setEditItem(newItem)
      } else if (picker.target === 'co') {
        const newCOItem = await addChangeOrderItem(picker.coId, {
          description: material.description || 'New item',
          qty: '1',
          unit_price: String(material.unit_price ?? '0.00'),
        })
        await fetchEstimate()
        addToast('Item added from materials')
        // Open the CO edit modal so user can adjust qty/price
        setEditCOItem({ coId: picker.coId, item: newCOItem })
      }
    } catch {
      addToast('Failed to add material', 'error')
    }
  }

  const handleDuplicateItem = async (itemId) => {
    try {
      await duplicateLineItem(id, itemId)
      await fetchEstimate()
      addToast('Item duplicated')
    } catch {
      addToast('Failed to duplicate item', 'error')
    }
  }

  const handleDuplicateCOItem = async (coId, itemId) => {
    try {
      await duplicateChangeOrderItem(coId, itemId)
      await fetchEstimate()
      addToast('Item duplicated')
    } catch {
      addToast('Failed to duplicate item', 'error')
    }
  }

  const handleDeleteItem = async () => {
    if (!deleteItemId) return
    try {
      await deleteLineItem(id, deleteItemId)
      setDeleteItemId(null)
      fetchEstimate()
    } catch {
      addToast('Failed to delete item', 'error')
    }
  }

  const handleDuplicate = async () => {
    try {
      const est = await duplicateEstimate(id)
      addToast('Estimate duplicated')
      navigate(`/estimates/${est.id}`)
    } catch {
      addToast('Failed to duplicate', 'error')
    }
  }

  const handleCreateInvoice = async () => {
    try {
      const inv = await createInvoice({ estimate_id: Number(id) })
      addToast('Invoice created')
      navigate(`/invoices/${inv.id}`)
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create invoice', 'error')
    }
  }

  // Sprint 15d — internal approve
  const handleInternalApprove = async () => {
    if (!window.confirm(
      'Mark this estimate approved? This moves it into the Jobs pipeline under "Pending Schedule".'
    )) return
    try {
      await approveEstimateInternal(id, { signerName: 'internal' })
      addToast('Estimate approved')
      fetchEstimate()
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to approve estimate', 'error')
    }
  }

  // Sprint 15d — deposit invoice
  const handleCreateDepositInvoice = async () => {
    const input = window.prompt('Deposit percentage (1-99):', '50')
    if (input === null) return
    const percent = Number(input)
    if (!Number.isFinite(percent) || percent <= 0 || percent >= 100) {
      addToast('Deposit percent must be between 1 and 99', 'error')
      return
    }
    try {
      const inv = await createDepositInvoice({
        estimateId: Number(id),
        depositPercent: percent,
      })
      addToast('Deposit invoice created')
      navigate(`/invoices/${inv.id}`)
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create deposit invoice', 'error')
    }
  }

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`/api/estimates/${id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('PDF generation failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Estimate_${(estimate?.name || 'Estimate').replace(/\s+/g, '_')}_${id}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      addToast('Failed to generate PDF', 'error')
    } finally {
      setPdfLoading(false)
    }
  }

  const getPreviewUrl = () => {
    const token = localStorage.getItem('access_token')
    return `/api/estimates/${id}/preview?token=${encodeURIComponent(token)}`
  }

  const handleOpenSendModal = () => {
    setSendForm({
      to_email: estimate?.contact_email || '',
      subject: 'Estimate from Legacy Roofing & Exteriors',
      message: `Please find attached your estimate for ${estimate?.name || 'your project'}.`,
    })
    setShowSendModal(true)
  }

  const handleSendEstimate = async () => {
    if (!sendForm.to_email) {
      addToast('Email address is required', 'error')
      return
    }
    setSendLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`/api/estimates/${id}/send`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(sendForm),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to send')
      addToast(`Estimate sent to ${sendForm.to_email}`)
      setShowSendModal(false)
      fetchEstimate()
    } catch (err) {
      addToast(err.message || 'Failed to send estimate', 'error')
    } finally {
      setSendLoading(false)
    }
  }

  const handleSettingChange = async (field, value) => {
    setEstimate((prev) => ({ ...prev, [field]: value }))
    try {
      await updateEstimate(id, { [field]: value })
      fetchEstimate()
    } catch {
      addToast('Failed to update setting', 'error')
      fetchEstimate()
    }
  }

  // Section handlers
  const handleCreateSection = async (data) => {
    try {
      await createSection(id, data)
      fetchEstimate()
    } catch {
      addToast('Failed to create section', 'error')
    }
  }

  const handleUpdateSection = async (data) => {
    try {
      await updateSection(id, sectionModal.section.id, data)
      fetchEstimate()
    } catch {
      addToast('Failed to update section', 'error')
    }
  }

  const handleDeleteSection = async () => {
    if (!deleteSectionId) return
    try {
      await deleteSection(id, deleteSectionId)
      setDeleteSectionId(null)
      fetchEstimate()
    } catch {
      addToast('Failed to delete section', 'error')
    }
  }

  const toggleSection = (sectionId) => {
    setCollapsedSections((prev) => ({ ...prev, [sectionId]: !prev[sectionId] }))
  }

  // Change order handlers
  const handleCreateChangeOrder = async () => {
    try {
      const newCO = await createChangeOrder(id, { name: '' })
      await fetchEstimate()
      setTimeout(() => {
        const el = document.getElementById(`co-${newCO.id}`)
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    } catch {
      addToast('Failed to create change order', 'error')
    }
  }

  const handleUpdateCOName = async (coId, name) => {
    try {
      await updateChangeOrder(coId, { name })
      setEditCOName(null)
      fetchEstimate()
    } catch {
      addToast('Failed to update change order', 'error')
    }
  }

  const handleUpdateCOStatus = async (coId, status) => {
    try {
      await updateChangeOrder(coId, { status })
      fetchEstimate()
    } catch {
      addToast('Failed to update status', 'error')
    }
  }

  const handleDeleteChangeOrder = async () => {
    if (!deleteCOId) return
    try {
      await deleteChangeOrderApi(deleteCOId)
      setDeleteCOId(null)
      fetchEstimate()
    } catch {
      addToast('Failed to delete change order', 'error')
    }
  }

  const handleAddCOItem = async (coId) => {
    try {
      await addChangeOrderItem(coId, {
        description: 'New item',
        qty: '1',
        unit_price: '0.00',
      })
      fetchEstimate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const handleCOItemSave = async (itemId, values) => {
    if (!editCOItem) return
    try {
      await updateChangeOrderItem(editCOItem.coId, itemId, values)
      fetchEstimate()
    } catch {
      addToast('Failed to update item', 'error')
    }
  }

  const handleDeleteCOItem = async () => {
    if (!deleteCOItemTarget) return
    try {
      await deleteChangeOrderItem(deleteCOItemTarget.coId, deleteCOItemTarget.itemId)
      setDeleteCOItemTarget(null)
      fetchEstimate()
    } catch {
      addToast('Failed to delete item', 'error')
    }
  }

  const handleOpenSendCOModal = (co) => {
    setSendCOForm({
      to_email: estimate?.contact_email || '',
      subject: `Change Order #${co.co_number} from Legacy Roofing & Exteriors`,
      message: `Please review the attached change order for ${estimate?.name || 'your project'}.`,
    })
    setSendCOModal(co)
  }

  const handleSendCO = async () => {
    if (!sendCOModal || !sendCOForm.to_email) return
    setSendCOLoading(true)
    try {
      await sendChangeOrder(sendCOModal.id, sendCOForm)
      addToast(`Change order sent to ${sendCOForm.to_email}`)
      setSendCOModal(null)
      fetchEstimate()
    } catch (err) {
      addToast(err.message || 'Failed to send change order', 'error')
    } finally {
      setSendCOLoading(false)
    }
  }

  if (loading) {
    return <LoadingSpinner centered />
  }

  if (!estimate) {
    return (
      <div className="text-center py-16">
        <p className="text-th-text-secondary">Estimate not found</p>
        <button
          onClick={() => navigate(-1)}
          className="text-brand-purple hover:text-brand-purple-text mt-2 text-sm"
        >
          Go back
        </button>
      </div>
    )
  }

  const lineItems = estimate.line_items || []
  const sections = estimate.sections || []
  const depositAmt =
    estimate.deposit_percent && estimate.total
      ? (parseFloat(estimate.total) * parseFloat(estimate.deposit_percent)) / 100
      : null

  const showQty = estimate.show_quantities
  const showPrice = estimate.show_unit_prices
  const showTotal = estimate.show_line_totals
  const showSubtotal = estimate.show_subtotal

  // Split items: unsectioned vs sectioned
  const sectionIds = new Set(sections.map((s) => s.id))
  const unsectionedItems = lineItems.filter((li) => !li.section_id || !sectionIds.has(li.section_id))

  const tabs = [
    { key: 'items', label: 'Line Items' },
    { key: 'notes', label: 'Notes' },
    { key: 'files', label: fileCount > 0 ? `Files (${fileCount})` : 'Files' },
  ]

  return (
    <div className="max-w-full overflow-x-hidden">
      {estimate.contact_id ? (
        <BackButton
          to={`/contacts/${estimate.contact_id}`}
          label={`Back to ${estimate.contact_name || 'Client'}`}
        />
      ) : (
        <BackButton to="/estimates" label="Back to Estimates" />
      )}

      {/* Breadcrumb — Sprint 15e: client-centric navigation */}
      <div className="flex items-center gap-2 text-sm text-th-text-muted mb-4">
        <Link to="/contacts" className="hover:text-th-text transition-colors">
          Clients
        </Link>
        <span>/</span>
        {estimate.contact_id && (
          <>
            <Link
              to={`/contacts/${estimate.contact_id}`}
              className="hover:text-th-text transition-colors"
            >
              {estimate.contact_name || 'Client'}
            </Link>
            <span>/</span>
          </>
        )}
        <span className="text-th-text">{estimate.name || `Estimate #${estimate.id}`}</span>
      </div>

      {/* Header: title left, compact settings right */}
      <div className="flex items-start justify-between mb-2 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="min-w-0">
            {editingName ? (
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onBlur={handleNameSave}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') e.target.blur()
                  if (e.key === 'Escape') {
                    setNameValue(estimate.name)
                    setEditingName(false)
                  }
                }}
                className="text-2xl font-bold bg-surface border border-th-border-secondary rounded-lg px-3 py-1 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
                autoFocus
              />
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <h1
                  onClick={() => setEditingName(true)}
                  className="text-2xl font-bold text-th-text cursor-text hover:text-brand-purple transition-colors break-words"
                >
                  {estimate.name || `Estimate #${estimate.id}`}
                </h1>
                <EstimateStatusBadge status={estimate.status} />
              </div>
            )}
            {estimate.job_address && (
              <p className="text-sm text-th-text-muted mt-0.5">
                {estimate.job_address}
              </p>
            )}
          </div>
        </div>

        {/* Compact display settings */}
        <div className="shrink-0 flex flex-col items-end gap-1.5 pt-1">
          <div className="flex items-center gap-3">
            <MiniToggle label="Qty" title="Show Quantities" checked={estimate.show_quantities} onChange={(v) => handleSettingChange('show_quantities', v)} />
            <MiniToggle label="Price" title="Show Unit Prices" checked={estimate.show_unit_prices} onChange={(v) => handleSettingChange('show_unit_prices', v)} />
            <MiniToggle label="Totals" title="Show Line Totals" checked={estimate.show_line_totals} onChange={(v) => handleSettingChange('show_line_totals', v)} />
            <MiniToggle label="Sub" title="Show Subtotal" checked={estimate.show_subtotal} onChange={(v) => handleSettingChange('show_subtotal', v)} />
            <MiniToggle label="Tax Incl" title="Tax Included in Prices" checked={estimate.tax_included} onChange={(v) => handleSettingChange('tax_included', v)} />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1" title="Deposit Percent">
              <span className="text-[11px] text-th-text-muted">Dep%</span>
              <input
                type="number"
                step="0.01"
                value={estimate.deposit_percent ?? ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? null : e.target.value
                  setEstimate((prev) => ({ ...prev, deposit_percent: val }))
                }}
                onBlur={(e) => {
                  const val = e.target.value === '' ? null : parseFloat(e.target.value)
                  handleSettingChange('deposit_percent', val)
                }}
                placeholder="--"
                className="w-14 bg-page border border-th-border rounded px-1.5 py-0.5 text-[11px] font-mono text-th-text text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div className="flex items-center gap-1" title="Tax Rate">
              <span className="text-[11px] text-th-text-muted">Tax%</span>
              <input
                type="number"
                step="0.01"
                value={taxValue}
                onChange={(e) => setTaxValue(e.target.value)}
                onBlur={handleTaxSave}
                className="w-14 bg-page border border-th-border rounded px-1.5 py-0.5 text-[11px] font-mono text-th-text text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <button
          onClick={() => setShowApplyTemplate(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
        >
          <FileText size={15} />
          Apply Template
        </button>
        <button
          onClick={handleDuplicate}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
        >
          <Copy size={15} />
          Duplicate
        </button>
        <button
          onClick={handleDownloadPdf}
          disabled={pdfLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
        >
          {pdfLoading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
          {pdfLoading ? 'Generating...' : 'Download PDF'}
        </button>
        <button
          onClick={() => setShowCustomerView(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
        >
          <Eye size={15} />
          Customer View
        </button>
        <button
          onClick={handleOpenSendModal}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
        >
          <Mail size={15} />
          Send Estimate
        </button>
        <WorkOrderDropdown
          estimateId={Number(id)}
          onSend={(secret) => setWoSend({ secret })}
        />
        {estimate.contact_phone && (
          <button
            onClick={() => setShowSmsConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
          >
            <MessageCircle size={15} />
            Send via Text
          </button>
        )}
        {/* Sprint 16c — AI chat panel button */}
        <AIPanelButton
          mode="entity"
          entityType="estimate"
          entityId={Number(id)}
          label="Chat"
        />
        {/* Sprint 15d — internal approve visible on non-approved, non-closed estimates */}
        {['draft', 'sent', 'viewed'].includes(estimate.status) && (
          <button
            onClick={handleInternalApprove}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-btn-primary-text bg-btn-primary-bg hover:bg-btn-primary-hover rounded-lg transition-colors"
          >
            <CheckCircle2 size={15} />
            Internal Approve
          </button>
        )}
        {/* Sprint 15d — deposit invoice available anytime the estimate has a total */}
        {Number(estimate.total || 0) > 0 && (
          <button
            onClick={handleCreateDepositInvoice}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-purple-400 hover:text-purple-300 hover:bg-surface rounded-lg transition-colors"
          >
            <Receipt size={15} />
            Deposit Invoice
          </button>
        )}
        {estimate.status === 'approved' && (
          <button
            onClick={handleCreateChangeOrder}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-brand-purple hover:text-brand-purple-text hover:bg-surface rounded-lg transition-colors"
          >
            <Plus size={15} />
            New Change Order
          </button>
        )}
        {estimate.status === 'approved' && !estimate.invoice_id && (
          <button
            onClick={handleCreateInvoice}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-btn-primary-text bg-green-500 hover:bg-green-600 rounded-lg transition-colors"
          >
            <FileText size={15} />
            Create Invoice
          </button>
        )}
        {estimate.invoice_id && (
          <Link
            to={`/invoices/${estimate.invoice_id}`}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-green-400 hover:text-green-300 hover:bg-surface rounded-lg transition-colors"
          >
            <FileText size={15} />
            View Invoice
          </Link>
        )}
      </div>

      {/* Sprint 14.5: Estimate metadata panel */}
      <div className="bg-surface rounded-xl p-4 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="space-y-1 min-w-0">
          <div className="text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Customer
          </div>
          {estimate.contact_company && (
            <div className="text-th-text font-semibold truncate">
              {estimate.contact_company}
            </div>
          )}
          <div className="text-th-text truncate">
            {estimate.contact_name || '—'}
          </div>
          {estimate.contact_address && (
            <div className="text-th-text-secondary truncate">
              <AddressLink address={estimate.contact_address} />
            </div>
          )}
          {estimate.contact_phone && (
            <div className="text-th-text-secondary">
              <PhoneLink phone={estimate.contact_phone} />
            </div>
          )}
          {estimate.contact_email && (
            <div className="text-th-text-secondary truncate">
              <a
                href={`mailto:${estimate.contact_email}`}
                className="hover:text-brand-purple transition-colors"
              >
                {estimate.contact_email}
              </a>
            </div>
          )}
          {estimate.job_address && estimate.job_address !== estimate.contact_address && (
            <div className="text-th-text-muted text-xs mt-2">
              <span className="uppercase tracking-wider">Property:</span>{' '}
              <AddressLink
                address={estimate.job_address}
                className="text-th-text-secondary"
              />
            </div>
          )}
        </div>
        <div className="space-y-1 min-w-0">
          <div className="text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Estimate Details
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-th-text-muted">Number</span>
            <span className="text-th-text font-mono">#{estimate.id}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-th-text-muted">Created</span>
            <span className="text-th-text font-mono">
              {estimate.created_at
                ? new Date(estimate.created_at).toLocaleDateString()
                : '—'}
            </span>
          </div>
          <div className="flex justify-between gap-2 items-center">
            <span className="text-th-text-muted">Expiration</span>
            <input
              type="date"
              value={estimate.expiration_date || ''}
              onChange={(e) =>
                setEstimate((prev) => ({
                  ...prev,
                  expiration_date: e.target.value || null,
                }))
              }
              onBlur={(e) => handleSettingChange('expiration_date', e.target.value || null)}
              className="bg-page border border-th-border rounded px-2 py-0.5 text-xs font-mono text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-th-text-muted">Salesperson</span>
            <span className="text-th-text truncate">
              {estimate.created_by_user_name || '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Sprint 15d — Job Info panel (visible once the estimate is approved) */}
      {['approved', 'in_progress', 'complete', 'closed'].includes(estimate.status) && (
        <div className="bg-surface rounded-xl p-4 mb-6 border border-brand-purple/20">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Briefcase size={14} className="text-brand-purple-text" />
              <h3 className="text-xs font-semibold text-th-text uppercase tracking-wider">
                Job Info
              </h3>
            </div>
            {/* Status transition dropdown */}
            <div className="flex items-center gap-2">
              <label className="text-[11px] text-th-text-muted uppercase tracking-wider">
                Status
              </label>
              <select
                value={estimate.status}
                onChange={(e) => handleSettingChange('status', e.target.value)}
                className="bg-page border border-th-border rounded px-2 py-1 text-xs text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="approved">Approved</option>
                <option value="in_progress">In Progress</option>
                <option value="complete">Complete</option>
                <option value="closed">Closed</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3 text-sm">
            {/* Job Type */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Job Type
              </label>
              <input
                type="text"
                value={estimate.job_type || ''}
                onChange={(e) =>
                  setEstimate((prev) => ({ ...prev, job_type: e.target.value }))
                }
                onBlur={(e) => {
                  const val = e.target.value || null
                  handleSettingChange('job_type', val)
                  if (val) {
                    const lower = val.toLowerCase()
                    if (lower === 'painting') handleSettingChange('tax_included', true)
                    else if (lower === 'roofing') handleSettingChange('tax_included', false)
                  }
                }}
                placeholder="e.g. Roofing"
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:border-th-border-focus"
              />
            </div>

            {/* Work Type */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Work Type
              </label>
              <select
                value={estimate.work_type || ''}
                onChange={(e) => handleSettingChange('work_type', e.target.value || null)}
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">—</option>
                <option value="retail">Retail</option>
                <option value="insurance">Insurance</option>
              </select>
            </div>

            {/* Crew */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Crew
              </label>
              <select
                value={estimate.crew_id || ''}
                onChange={(e) =>
                  handleSettingChange('crew_id', e.target.value ? Number(e.target.value) : null)
                }
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">Unassigned</option>
                {crewOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Scheduled Start */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Scheduled Start
              </label>
              <input
                type="date"
                value={estimate.scheduled_start || ''}
                onChange={(e) =>
                  setEstimate((prev) => ({
                    ...prev,
                    scheduled_start: e.target.value || null,
                  }))
                }
                onBlur={(e) =>
                  handleSettingChange('scheduled_start', e.target.value || null)
                }
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm font-mono text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>

            {/* Scheduled End */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Scheduled End
              </label>
              <input
                type="date"
                value={estimate.scheduled_end || ''}
                onChange={(e) =>
                  setEstimate((prev) => ({
                    ...prev,
                    scheduled_end: e.target.value || null,
                  }))
                }
                onBlur={(e) =>
                  handleSettingChange('scheduled_end', e.target.value || null)
                }
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm font-mono text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>

            {/* Assigned To */}
            <div>
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Assigned To
              </label>
              <select
                value={estimate.assigned_to_user_id || ''}
                onChange={(e) =>
                  handleSettingChange(
                    'assigned_to_user_id',
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">Unassigned</option>
                {employeeOptions.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.full_name}
                  </option>
                ))}
              </select>
            </div>

            {/* Location Address — full width */}
            <div className="md:col-span-2 lg:col-span-3">
              <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
                Location Address
              </label>
              <input
                type="text"
                value={estimate.location_address || ''}
                onChange={(e) =>
                  setEstimate((prev) => ({
                    ...prev,
                    location_address: e.target.value,
                  }))
                }
                onBlur={(e) =>
                  handleSettingChange('location_address', e.target.value || null)
                }
                placeholder="Job site address"
                className="w-full bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>
        </div>
      )}

      {/* Sprint 16b — AI-generated scope of work */}
      {estimate.scope_of_work && (
        <div className="bg-surface rounded-xl p-4 mb-6 border-l-4 border-brand-purple">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-th-text-muted">
              <Sparkles size={12} className="text-brand-purple" />
              Scope of Work
            </div>
            <button
              onClick={async () => {
                if (!confirm('Remove scope of work?')) return
                await updateEstimate(id, { scope_of_work: null })
                await fetchEstimate()
              }}
              className="text-[11px] text-th-text-muted hover:text-th-text"
            >
              Clear
            </button>
          </div>
          <p className="text-sm text-th-text whitespace-pre-wrap leading-relaxed">
            {estimate.scope_of_work}
          </p>
        </div>
      )}

      {/* Tab strip */}
      <div className="flex gap-6 mb-6 border-b border-th-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`pb-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? 'text-brand-purple border-brand-purple'
                : 'text-th-text-muted border-transparent hover:text-th-text'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'notes' && (
        <NotesTab entityType="estimate" entityId={Number(id)} />
      )}
      {activeTab === 'files' && (
        <FilesTab
          entityType="estimate"
          entityId={Number(id)}
          onCountChange={setFileCount}
        />
      )}
      {activeTab === 'items' && (
        <>
          {/* Line Items Table */}
          <div className="bg-surface rounded-xl overflow-hidden mb-6">
            {/* Table Header */}
            <div className="flex items-center gap-2 px-3 py-2.5 border-b border-th-border text-xs font-medium text-th-text-muted uppercase tracking-wider">
              <div className="w-[14px] shrink-0" />
              <div className="flex-1">Description</div>
              <div className="w-[27px] shrink-0" />
              {showQty && <div className="w-12 sm:w-16 shrink-0 text-right">Qty</div>}
              {showPrice && <div className="w-20 sm:w-24 shrink-0 text-right">Price</div>}
              {showTotal && <div className="w-20 sm:w-24 shrink-0 text-right">Total</div>}
              <div className="w-[14px] shrink-0" />
            </div>

            {/* Unsectioned items first */}
            {unsectionedItems.length > 0 && (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={unsectionedItems.map((i) => i.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="divide-y divide-th-border/50">
                    {unsectionedItems.map((item) => (
                      <SortableRow
                        key={item.id}
                        item={item}
                        onEdit={setEditItem}
                        onDelete={setDeleteItemId}
                        onDuplicate={handleDuplicateItem}
                        showQty={showQty}
                        showPrice={showPrice}
                        showTotal={showTotal}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}

            {/* Sections */}
            {sections.map((section) => {
              const sectionItems = lineItems.filter((li) => li.section_id === section.id)
              const isCollapsed = collapsedSections[section.id]

              return (
                <div key={section.id}>
                  <SectionHeader
                    section={section}
                    onEdit={() => setSectionModal({ open: true, section })}
                    onDelete={() => setDeleteSectionId(section.id)}
                    onAddItem={() => handleAddItem(section.id)}
                    onAddFromMaterials={() => openMaterialPickerForEstimate(section.id)}
                    showTotal={showTotal}
                    collapsed={isCollapsed}
                    onToggle={() => toggleSection(section.id)}
                  />
                  {!isCollapsed && sectionItems.length > 0 && (
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragEnd={handleDragEnd}
                    >
                      <SortableContext
                        items={sectionItems.map((i) => i.id)}
                        strategy={verticalListSortingStrategy}
                      >
                        <div className="divide-y divide-th-border/50 ml-4">
                          {sectionItems.map((item) => (
                            <SortableRow
                              key={item.id}
                              item={item}
                              onEdit={setEditItem}
                              onDelete={setDeleteItemId}
                              onDuplicate={handleDuplicateItem}
                              showQty={showQty}
                              showPrice={showPrice}
                              showTotal={showTotal}
                            />
                          ))}
                        </div>
                      </SortableContext>
                    </DndContext>
                  )}
                  {!isCollapsed && sectionItems.length === 0 && (
                    <div className="px-3 py-4 text-center text-th-text-muted text-xs ml-4">
                      No items in this section
                    </div>
                  )}
                </div>
              )
            })}

            {lineItems.length === 0 && sections.length === 0 && (
              <div className="px-3 py-8 text-center text-th-text-muted text-sm">
                No line items yet
              </div>
            )}

            {/* Bottom buttons */}
            <div className="flex items-center gap-2 border-t border-th-border px-3 py-2">
              <AddItemSplitButton
                onAddBlank={() => handleAddItem()}
                onAddFromMaterials={() => openMaterialPickerForEstimate(null)}
              />
              <button
                onClick={() => setSectionModal({ open: true, section: null })}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-th-text-muted hover:text-brand-purple hover:bg-surface-hover/30 transition-colors rounded"
              >
                <FolderPlus size={14} />
                Add Section
              </button>
            </div>
          </div>

          {/* Change Orders */}
          {(estimate.change_orders || []).map((co) => (
            <div key={co.id} id={`co-${co.id}`} className="bg-surface rounded-xl overflow-hidden mb-6">
              {/* CO Header */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-th-border">
                <span className="text-sm font-semibold text-th-text">
                  Change Order #{co.co_number}
                </span>
                {co.status === 'approved' && co.accepted_at ? (
                  <span className="inline-flex items-center rounded-full bg-green-600 px-2 py-0.5 text-xs text-white">
                    Accepted {new Date(co.accepted_at).toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' })}
                  </span>
                ) : (
                  <EstimateStatusBadge status={co.status} />
                )}
                <span className="text-xs text-th-text-muted">
                  {co.created_at ? new Date(co.created_at).toLocaleDateString() : ''}
                </span>
                <div className="flex-1" />
                {co.status === 'draft' && (
                  <button
                    onClick={() => handleUpdateCOStatus(co.id, 'approved')}
                    className="text-xs text-green-500 hover:text-green-400 px-2 py-1 rounded transition-colors"
                  >
                    Approve
                  </button>
                )}
                {co.status === 'approved' && (
                  <button
                    onClick={() => handleUpdateCOStatus(co.id, 'draft')}
                    className="text-xs text-th-text-muted hover:text-th-text px-2 py-1 rounded transition-colors"
                  >
                    Revert to Draft
                  </button>
                )}
                {(co.status === 'draft' || co.status === 'changes_requested') && (co.items || []).length > 0 && (
                  <button
                    onClick={() => handleOpenSendCOModal(co)}
                    className="flex items-center gap-1 text-xs text-th-text-secondary hover:text-th-text px-2 py-1 rounded transition-colors"
                  >
                    <Mail size={13} />
                    Send
                  </button>
                )}
                <button
                  onClick={() => setDeleteCOId(co.id)}
                  className="text-th-text-muted hover:text-red-400 transition-colors p-1"
                  title="Delete change order"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {/* CO Name (editable) */}
              <div className="px-4 py-2 border-b border-th-border/50">
                {editCOName && editCOName.coId === co.id ? (
                  <input
                    type="text"
                    value={editCOName.name}
                    onChange={(e) => setEditCOName({ ...editCOName, name: e.target.value })}
                    onBlur={() => handleUpdateCOName(co.id, editCOName.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') e.target.blur()
                      if (e.key === 'Escape') setEditCOName(null)
                    }}
                    className="bg-page border border-th-border rounded px-2 py-1 text-sm text-th-text focus:outline-none focus:border-th-border-focus w-full"
                    autoFocus
                    placeholder="Change order name (optional)"
                  />
                ) : (
                  <span
                    onClick={() => setEditCOName({ coId: co.id, name: co.name || '' })}
                    className="text-sm text-th-text-secondary cursor-text hover:text-brand-purple transition-colors"
                  >
                    {co.name || 'Add description...'}
                  </span>
                )}
              </div>

              {/* CO Items Header */}
              <div className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-th-text-muted uppercase tracking-wider border-b border-th-border/50">
                <div className="flex-1">Description</div>
                {showQty && <div className="w-12 sm:w-16 shrink-0 text-right">Qty</div>}
                {showPrice && <div className="w-20 sm:w-24 shrink-0 text-right">Price</div>}
                {showTotal && <div className="w-20 sm:w-24 shrink-0 text-right">Total</div>}
                <div className="w-[14px] shrink-0" />
              </div>

              {/* CO Items */}
              {(co.items || []).length > 0 ? (
                <div className="divide-y divide-th-border/50">
                  {co.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-2 px-3 py-2 group hover:bg-surface-hover/30 transition-colors"
                    >
                      <div
                        className="flex-1 min-w-0 cursor-pointer"
                        onClick={() => setEditCOItem({ coId: co.id, item })}
                      >
                        <span className="text-sm text-th-text block truncate">
                          {item.description || 'Untitled item'}
                        </span>
                        {item.body && (
                          <span className="text-xs text-th-text-muted block truncate mt-0.5">
                            {stripHtml(item.body)}
                          </span>
                        )}
                      </div>
                      <button
                        onClick={() => setEditCOItem({ coId: co.id, item })}
                        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-brand-purple transition-all shrink-0 p-1"
                        title="Edit item"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        onClick={() => handleDuplicateCOItem(co.id, item.id)}
                        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-brand-purple transition-all shrink-0 p-1"
                        title="Duplicate item"
                      >
                        <Copy size={13} />
                      </button>
                      {showQty && (
                        <div className="w-12 sm:w-16 shrink-0 text-right">
                          <span className="text-sm font-mono text-th-text">
                            {parseFloat(item.qty)}
                          </span>
                        </div>
                      )}
                      {showPrice && (
                        <div className="w-20 sm:w-24 shrink-0 text-right">
                          <span className="text-sm font-mono text-th-text">
                            {formatCurrency(item.unit_price)}
                          </span>
                        </div>
                      )}
                      {showTotal && (
                        <div className="w-20 sm:w-24 shrink-0 text-right">
                          <span className="text-sm font-mono text-th-text">
                            {formatCurrency(item.line_total)}
                          </span>
                        </div>
                      )}
                      <button
                        onClick={() => setDeleteCOItemTarget({ coId: co.id, itemId: item.id })}
                        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all shrink-0"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-3 py-4 text-center text-th-text-muted text-xs">
                  No items yet
                </div>
              )}

              {/* Add Item + CO Subtotal */}
              <div className="flex items-center border-t border-th-border px-3 py-2">
                <div className="flex-1">
                  <AddItemSplitButton
                    onAddBlank={() => handleAddCOItem(co.id)}
                    onAddFromMaterials={() => openMaterialPickerForCO(co.id)}
                  />
                </div>
                {showTotal && (
                  <div className="text-right">
                    <span className="text-xs text-th-text-muted mr-2">CO Subtotal:</span>
                    <span className="text-sm font-mono text-th-text">{formatCurrency(co.subtotal)}</span>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Totals */}
          <div className="bg-surface rounded-xl p-4 max-w-sm ml-auto mb-6">
            <div className="space-y-2">
              {showSubtotal && (() => {
                const approvedCOTotal = (estimate.change_orders || [])
                  .filter((co) => co.status === 'approved')
                  .reduce((sum, co) => sum + parseFloat(co.total || 0), 0)
                const hasApprovedCOs = approvedCOTotal > 0

                return (
                  <>
                    {hasApprovedCOs && (
                      <>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-th-text-secondary">Estimate Subtotal</span>
                          <span className="font-mono text-th-text">
                            {formatCurrency(estimate.subtotal)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-th-text-secondary">Change Orders</span>
                          <span className="font-mono text-th-text">
                            {formatCurrency(approvedCOTotal)}
                          </span>
                        </div>
                        <div className="border-t border-th-border pt-2" />
                      </>
                    )}
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-th-text-secondary">Subtotal</span>
                      <span className="font-mono text-th-text">
                        {formatCurrency(
                          hasApprovedCOs
                            ? parseFloat(estimate.subtotal || 0) + (estimate.change_orders || [])
                                .filter((co) => co.status === 'approved')
                                .reduce((sum, co) => sum + parseFloat(co.subtotal || 0), 0)
                            : estimate.subtotal
                        )}
                      </span>
                    </div>
                  </>
                )
              })()}
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-th-text-secondary">Tax</span>
                  {estimate.tax_included ? (
                    <span
                      className="text-xs text-th-text-muted font-mono opacity-50 cursor-not-allowed"
                      title="Tax is included in line item prices"
                    >
                      ({(parseFloat(estimate.tax_rate) * 100).toFixed(2)}%)
                    </span>
                  ) : editingTax ? (
                    <input
                      type="number"
                      step="0.01"
                      value={taxValue}
                      onChange={(e) => setTaxValue(e.target.value)}
                      onBlur={handleTaxSave}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') e.target.blur()
                        if (e.key === 'Escape') {
                          setTaxValue(
                            (parseFloat(estimate.tax_rate) * 100).toFixed(2)
                          )
                          setEditingTax(false)
                        }
                      }}
                      className="w-16 bg-surface-hover border border-th-border-secondary rounded px-2 py-0.5 text-xs text-th-text font-mono text-right focus:outline-none focus:ring-1 focus:ring-brand-purple/50"
                      autoFocus
                    />
                  ) : (
                    <span
                      onClick={() => setEditingTax(true)}
                      className="text-xs text-th-text-muted cursor-text hover:text-brand-purple transition-colors font-mono"
                    >
                      ({(parseFloat(estimate.tax_rate) * 100).toFixed(2)}%)
                    </span>
                  )}
                </div>
                <span className="font-mono text-th-text">
                  {estimate.tax_included
                    ? 'Included'
                    : formatCurrency(
                        parseFloat(estimate.tax || 0) + (estimate.change_orders || [])
                          .filter((co) => co.status === 'approved')
                          .reduce((sum, co) => sum + parseFloat(co.tax || 0), 0)
                      )
                  }
                </span>
              </div>
              {depositAmt !== null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-th-text-secondary">
                    Deposit ({parseFloat(estimate.deposit_percent)}%)
                  </span>
                  <span className="font-mono text-th-text">
                    {formatCurrency(depositAmt)}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t border-th-border">
                <span className="text-th-text font-semibold">Total</span>
                <span className="font-mono text-lg text-brand-purple font-bold">
                  {formatCurrency(estimate.grand_total || estimate.total)}
                </span>
              </div>
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        isOpen={deleteItemId !== null}
        onConfirm={handleDeleteItem}
        onCancel={() => setDeleteItemId(null)}
        title="Delete Line Item"
        message="Are you sure you want to delete this line item?"
        confirmLabel="Delete"
        variant="danger"
      />

      <ConfirmDialog
        isOpen={deleteSectionId !== null}
        onConfirm={handleDeleteSection}
        onCancel={() => setDeleteSectionId(null)}
        title="Delete Section"
        message="Items in this section will become unsectioned. Are you sure?"
        confirmLabel="Delete"
        variant="danger"
      />

      <ApplyTemplateModal
        open={showApplyTemplate}
        onClose={() => setShowApplyTemplate(false)}
        estimateId={id}
        onApplied={fetchEstimate}
      />


      <LineItemEditModal
        open={editItem !== null}
        item={editItem}
        sections={sections}
        onSave={handleItemSave}
        onClose={() => setEditItem(null)}
      />

      <LineItemEditModal
        open={editCOItem !== null}
        item={editCOItem?.item || null}
        sections={[]}
        onSave={handleCOItemSave}
        onClose={() => setEditCOItem(null)}
      />

      {materialPicker && (
        <MaterialPickerModal
          onClose={() => setMaterialPicker(null)}
          onSelect={handleMaterialSelected}
        />
      )}

      <ConfirmDialog
        isOpen={deleteCOItemTarget !== null}
        onConfirm={handleDeleteCOItem}
        onCancel={() => setDeleteCOItemTarget(null)}
        title="Delete Change Order Item"
        message="Are you sure you want to delete this item?"
        confirmLabel="Delete"
        variant="danger"
      />

      <ConfirmDialog
        isOpen={deleteCOId !== null}
        onConfirm={handleDeleteChangeOrder}
        onCancel={() => setDeleteCOId(null)}
        title="Delete Change Order"
        message="Are you sure you want to delete this change order and all its items?"
        confirmLabel="Delete"
        variant="danger"
      />

      {/* Send CO Modal */}
      {sendCOModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface rounded-xl w-full max-w-lg">
            <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
              <h2 className="text-lg font-semibold text-th-text">
                Send Change Order #{sendCOModal.co_number}
              </h2>
              <button
                onClick={() => setSendCOModal(null)}
                className="p-1.5 text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">To</label>
                <input
                  type="email"
                  value={sendCOForm.to_email}
                  onChange={(e) => setSendCOForm((f) => ({ ...f, to_email: e.target.value }))}
                  placeholder="customer@example.com"
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">Subject</label>
                <input
                  type="text"
                  value={sendCOForm.subject}
                  onChange={(e) => setSendCOForm((f) => ({ ...f, subject: e.target.value }))}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">Message</label>
                <textarea
                  value={sendCOForm.message}
                  onChange={(e) => setSendCOForm((f) => ({ ...f, message: e.target.value }))}
                  rows={4}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
                />
              </div>
              <button
                onClick={handleSendCO}
                disabled={sendCOLoading || !sendCOForm.to_email}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-th-text bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
              >
                {sendCOLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Mail size={16} />
                    Send Change Order
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <SectionEditModal
        open={sectionModal.open}
        section={sectionModal.section}
        onSave={sectionModal.section ? handleUpdateSection : handleCreateSection}
        onClose={() => setSectionModal({ open: false, section: null })}
      />

      <WorkOrderSendModal
        isOpen={!!woSend}
        estimateId={Number(id)}
        secret={woSend?.secret || false}
        defaultEmail={estimate?.contact_email || ''}
        onClose={() => setWoSend(null)}
        onSent={() => setWoSend(null)}
      />

      {/* Send via Text Confirm Modal — Sprint 17c */}
      {showSmsConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface rounded-xl w-full max-w-md">
            <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
              <h2 className="text-lg font-semibold text-th-text">Send Estimate via Text</h2>
              <button
                onClick={() => setShowSmsConfirm(false)}
                disabled={smsSending}
                className="p-1.5 text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors disabled:opacity-50"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <p className="text-sm text-th-text">
                Send the estimate portal link to{' '}
                <span className="font-medium">
                  {estimate?.contact_name || 'this client'}
                </span>{' '}
                at{' '}
                <span className="font-mono text-th-text">
                  {estimate?.contact_phone}
                </span>
                ?
              </p>
              <p className="text-xs text-th-text-muted">
                A text will be sent immediately. The client will be able to view
                and accept the estimate from their phone.
              </p>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowSmsConfirm(false)}
                  disabled={smsSending}
                  className="px-3 py-2 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSendViaText}
                  disabled={smsSending}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-brand-purple hover:bg-brand-purple/90 disabled:opacity-50 rounded-lg transition-colors"
                >
                  {smsSending ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Sending…
                    </>
                  ) : (
                    <>
                      <MessageCircle size={15} />
                      Send text
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Send Estimate Modal */}
      {showSendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface rounded-xl w-full max-w-lg">
            <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
              <h2 className="text-lg font-semibold text-th-text">Send Estimate</h2>
              <button
                onClick={() => setShowSendModal(false)}
                className="p-1.5 text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">To</label>
                <input
                  type="email"
                  value={sendForm.to_email}
                  onChange={(e) => setSendForm((f) => ({ ...f, to_email: e.target.value }))}
                  placeholder="customer@example.com"
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">Subject</label>
                <input
                  type="text"
                  value={sendForm.subject}
                  onChange={(e) => setSendForm((f) => ({ ...f, subject: e.target.value }))}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-sm text-th-text-secondary mb-1">Message</label>
                <textarea
                  value={sendForm.message}
                  onChange={(e) => setSendForm((f) => ({ ...f, message: e.target.value }))}
                  rows={4}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
                />
              </div>
              <button
                onClick={handleSendEstimate}
                disabled={sendLoading || !sendForm.to_email}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-th-text bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
              >
                {sendLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Mail size={16} />
                    Send Estimate
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Customer View Modal */}
      {showCustomerView && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface rounded-xl w-[95vw] max-w-5xl h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-th-border">
              <h2 className="text-lg font-semibold text-th-text">
                Customer View — {estimate?.name}
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadPdf}
                  disabled={pdfLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
                >
                  {pdfLoading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                  {pdfLoading ? 'Generating...' : 'Download PDF'}
                </button>
                <button
                  onClick={() => setShowCustomerView(false)}
                  className="p-1.5 text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <iframe
                src={getPreviewUrl()}
                title="Estimate Preview"
                className="w-full h-full border-0 rounded-b-xl bg-white"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
