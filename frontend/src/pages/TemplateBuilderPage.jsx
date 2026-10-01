import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, Plus, Save, Trash2, Search, X } from 'lucide-react'
import {
  getTemplate,
  updateTemplate,
  addTemplateItem,
  updateTemplateItem,
  deleteTemplateItem,
  previewTemplate,
  applyTemplate,
} from '../api/estimateTemplates'
import { listEstimates } from '../api/estimates'
import { listMaterials } from '../api/materials'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmDialog from '../components/ConfirmDialog'

const MEASUREMENT_TYPES = [
  { value: '', label: 'None (fixed qty)' },
  { value: 'total_area', label: 'Total Area (sq)' },
  { value: 'ridge', label: 'Ridge (LF)' },
  { value: 'hip', label: 'Hip (LF)' },
  { value: 'valley', label: 'Valley (LF)' },
  { value: 'eave', label: 'Eave (LF)' },
  { value: 'rake', label: 'Rake (LF)' },
]

const inputClass = 'bg-page border border-th-border rounded px-2 py-1.5 text-sm text-th-text focus:outline-none focus:border-th-border-focus w-full'
const smallInputClass = 'bg-page border border-th-border rounded px-2 py-1.5 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus w-full'

function MaterialPickerModal({ open, onClose, onSelect, onAddManual }) {
  const [materials, setMaterials] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    listMaterials({ search, perPage: 20 })
      .then((data) => setMaterials(data.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open, search])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">Add Item from Materials</h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text"><X size={20} /></button>
        </div>

        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search materials by name or item #..."
            className="w-full bg-page border border-th-border rounded-lg pl-9 pr-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
            autoFocus
          />
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : materials.length === 0 ? (
            <p className="text-center text-th-text-muted py-8 text-sm">No materials found</p>
          ) : (
            <div className="space-y-1">
              {materials.map((mat) => (
                <button
                  key={mat.id}
                  onClick={() => onSelect(mat)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-surface-hover/50 transition-colors text-left"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-th-text truncate">{mat.description}</p>
                    <p className="text-xs text-th-text-muted">{mat.item_number} &middot; {mat.category}</p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-sm font-mono text-th-text">
                      ${parseFloat(mat.unit_price).toFixed(2)}
                    </p>
                    <p className="text-xs text-th-text-muted">{mat.uom || '—'}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-th-border mt-4">
          <button
            onClick={onAddManual}
            className="w-full text-center text-sm text-brand-purple hover:text-brand-purple-text py-2 transition-colors"
          >
            + Add Manual Item (Labor, Custom, etc.)
          </button>
        </div>
      </div>
    </div>
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

function ApplyToJobModal({ open, onClose, templateId }) {
  const [estimates, setEstimates] = useState([])
  const [selectedEstimateId, setSelectedEstimateId] = useState('')
  const [measurements, setMeasurements] = useState({
    total_area: '', ridge: '', hip: '', valley: '', eave: '', rake: '',
  })
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const { addToast } = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    listEstimates({ perPage: 100 }).then((d) => setEstimates(d.items)).catch(() => {})
    setSelectedEstimateId('')
    setMeasurements({ total_area: '', ridge: '', hip: '', valley: '', eave: '', rake: '' })
    setPreview(null)
  }, [open])

  const handlePreview = async () => {
    if (!templateId) return
    setLoading(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      const data = await previewTemplate(templateId, { measurements: m })
      setPreview(data)
    } catch {
      addToast('Failed to generate preview', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    if (!selectedEstimateId || !templateId) return
    setApplying(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      await applyTemplate(selectedEstimateId, templateId, m)
      addToast('Template applied successfully')
      onClose()
      navigate(`/estimates/${selectedEstimateId}`)
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text flex items-center gap-2">
            <FileText size={20} className="text-brand-purple" />
            Apply Template to Estimate
          </h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text"><X size={20} /></button>
        </div>

        {/* Step 1: Select Estimate */}
        <div className="mb-4">
          <label className="block text-xs text-th-text-muted mb-1">Estimate</label>
          <select
            value={selectedEstimateId}
            onChange={(e) => setSelectedEstimateId(e.target.value)}
            className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
          >
            <option value="">Select an estimate...</option>
            {estimates.map((est) => (
              <option key={est.id} value={est.id}>
                {est.name}{est.job_address ? ` — ${est.job_address}` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Step 2: Measurements */}
        <div className="mb-4">
          <label className="block text-xs text-th-text-muted mb-2">Roof Measurements</label>
          <div className="grid grid-cols-3 gap-3">
            {measurementFields.map(({ key, label, unit }) => (
              <div key={key}>
                <span className="text-xs text-th-text-secondary">{label}</span>
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

        {/* Step 3: Preview */}
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

        {/* Step 4: Apply */}
        {preview && (
          <button
            onClick={handleApply}
            disabled={applying || !selectedEstimateId}
            className="w-full bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text font-semibold rounded-lg py-2.5 transition-colors"
          >
            {applying ? 'Applying...' : `Apply ${preview.item_count} Items to Estimate`}
          </button>
        )}
      </div>
    </div>
  )
}

function ItemRow({ item, templateId, onUpdate, onDelete }) {
  const [values, setValues] = useState({})
  const { addToast } = useToast()

  useEffect(() => {
    setValues({
      description: item.description,
      category: item.category,
      unit_cost: item.unit_cost,
      uom: item.uom || '',
      margin_pct: item.margin_pct,
      waste_pct: item.waste_pct,
      measurement_type: item.measurement_type || '',
      conversion_factor: item.conversion_factor,
      default_qty: item.default_qty || '',
    })
  }, [item])

  const handleBlur = async (field) => {
    const newVal = values[field]
    const oldVal = field === 'measurement_type'
      ? (item[field] || '')
      : item[field]

    if (String(newVal) === String(oldVal ?? '')) return

    const payload = { [field]: newVal === '' && field === 'measurement_type' ? null : newVal }
    try {
      await updateTemplateItem(templateId, item.id, payload)
      onUpdate()
    } catch {
      addToast('Failed to update item', 'error')
    }
  }

  return (
    <tr className="border-b border-th-border/50 hover:bg-surface-hover/20 transition-colors group">
      <td className="px-2 py-2">
        <input
          className={inputClass}
          value={values.category || ''}
          onChange={(e) => setValues((v) => ({ ...v, category: e.target.value }))}
          onBlur={() => handleBlur('category')}
          style={{ minWidth: '80px' }}
        />
      </td>
      <td className="px-2 py-2">
        <input
          className={inputClass}
          value={values.description || ''}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          onBlur={() => handleBlur('description')}
          style={{ minWidth: '120px' }}
        />
      </td>
      <td className="px-2 py-2 w-24">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.unit_cost || ''}
          onChange={(e) => setValues((v) => ({ ...v, unit_cost: e.target.value }))}
          onBlur={() => handleBlur('unit_cost')}
        />
      </td>
      <td className="px-2 py-2 w-16">
        <input
          className={inputClass + ' text-center'}
          value={values.uom || ''}
          onChange={(e) => setValues((v) => ({ ...v, uom: e.target.value }))}
          onBlur={() => handleBlur('uom')}
          style={{ minWidth: '40px' }}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.margin_pct || ''}
          onChange={(e) => setValues((v) => ({ ...v, margin_pct: e.target.value }))}
          onBlur={() => handleBlur('margin_pct')}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.waste_pct || ''}
          onChange={(e) => setValues((v) => ({ ...v, waste_pct: e.target.value }))}
          onBlur={() => handleBlur('waste_pct')}
        />
      </td>
      <td className="px-2 py-2 w-32">
        <select
          className={inputClass}
          value={values.measurement_type || ''}
          onChange={(e) => {
            setValues((v) => ({ ...v, measurement_type: e.target.value }))
            // Immediately save measurement_type changes
            const payload = { measurement_type: e.target.value || null }
            updateTemplateItem(templateId, item.id, payload).then(onUpdate).catch(() => {})
          }}
        >
          {MEASUREMENT_TYPES.map((mt) => (
            <option key={mt.value} value={mt.value}>{mt.label}</option>
          ))}
        </select>
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.0001"
          className={smallInputClass}
          value={values.conversion_factor || ''}
          onChange={(e) => setValues((v) => ({ ...v, conversion_factor: e.target.value }))}
          onBlur={() => handleBlur('conversion_factor')}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.default_qty || ''}
          onChange={(e) => setValues((v) => ({ ...v, default_qty: e.target.value }))}
          onBlur={() => handleBlur('default_qty')}
          placeholder={values.measurement_type ? '—' : '0'}
          disabled={!!values.measurement_type}
        />
      </td>
      <td className="px-2 py-2 w-8">
        <button
          onClick={() => onDelete(item.id)}
          className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all p-1"
        >
          <Trash2 size={14} />
        </button>
      </td>
    </tr>
  )
}

export default function TemplateBuilderPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [template, setTemplate] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState('')
  const [editingDesc, setEditingDesc] = useState(false)
  const [descValue, setDescValue] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [deleteItemId, setDeleteItemId] = useState(null)
  const [showApplyModal, setShowApplyModal] = useState(false)
  const [marginValue, setMarginValue] = useState('')
  const [wasteValue, setWasteValue] = useState('')
  const [saving, setSaving] = useState(false)

  const fetchTemplate = useCallback(async () => {
    try {
      const data = await getTemplate(id)
      setTemplate(data)
      setNameValue(data.name)
      setDescValue(data.description || '')
      setMarginValue(parseFloat(data.default_margin_pct))
      setWasteValue(parseFloat(data.default_waste_pct))
    } catch {
      addToast('Failed to load template', 'error')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchTemplate()
  }, [fetchTemplate])

  const handleNameSave = async () => {
    setEditingName(false)
    if (nameValue.trim() && nameValue.trim() !== template.name) {
      try {
        await updateTemplate(id, { name: nameValue.trim() })
        fetchTemplate()
      } catch (err) {
        addToast(err.response?.data?.detail || 'Failed to update name', 'error')
      }
    }
  }

  const handleDescSave = async () => {
    setEditingDesc(false)
    if (descValue !== (template.description || '')) {
      try {
        await updateTemplate(id, { description: descValue || null })
        fetchTemplate()
      } catch {
        addToast('Failed to update description', 'error')
      }
    }
  }

  const handleDefaultChange = async (field, value) => {
    try {
      await updateTemplate(id, { [field]: value })
      fetchTemplate()
    } catch {
      addToast('Failed to update default', 'error')
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateTemplate(id, {
        name: nameValue.trim() || template.name,
        description: descValue || null,
        default_margin_pct: marginValue,
        default_waste_pct: wasteValue,
      })
      await fetchTemplate()
      addToast('Template saved')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to save template', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleMaterialSelect = async (material) => {
    setShowPicker(false)
    try {
      await addTemplateItem(id, {
        material_id: material.id,
        description: material.description,
        category: material.category,
        unit_cost: material.unit_price,
        uom: material.uom,
      })
      fetchTemplate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const handleAddManual = async () => {
    setShowPicker(false)
    try {
      await addTemplateItem(id, {
        description: 'New Item',
        category: 'Labor',
        unit_cost: '0.00',
        waste_pct: '0.00',
      })
      fetchTemplate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const handleDeleteItem = async () => {
    if (!deleteItemId) return
    try {
      await deleteTemplateItem(id, deleteItemId)
      setDeleteItemId(null)
      fetchTemplate()
    } catch {
      addToast('Failed to delete item', 'error')
    }
  }

  if (loading) return <LoadingSpinner centered />
  if (!template) {
    return (
      <div className="text-center py-16">
        <p className="text-th-text-secondary">Template not found</p>
        <button onClick={() => navigate('/templates')} className="text-brand-purple hover:text-brand-purple-text mt-2 text-sm">
          Back to templates
        </button>
      </div>
    )
  }

  const items = template.items || []

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-th-text-muted mb-4">
        <Link to="/templates" className="hover:text-th-text transition-colors">Templates</Link>
        <span>/</span>
        <span className="text-th-text">{template.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/templates')}
            className="p-2 text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            {editingName ? (
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onBlur={handleNameSave}
                onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') { setNameValue(template.name); setEditingName(false) } }}
                className="text-2xl font-bold bg-surface border border-th-border-secondary rounded-lg px-3 py-1 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
                autoFocus
              />
            ) : (
              <h1
                onClick={() => setEditingName(true)}
                className="text-2xl font-bold text-th-text cursor-text hover:text-brand-purple transition-colors"
              >
                {template.name}
              </h1>
            )}
            {editingDesc ? (
              <input
                type="text"
                value={descValue}
                onChange={(e) => setDescValue(e.target.value)}
                onBlur={handleDescSave}
                onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') { setDescValue(template.description || ''); setEditingDesc(false) } }}
                className="mt-1 text-sm bg-surface border border-th-border-secondary rounded px-2 py-1 text-th-text-secondary focus:outline-none focus:ring-1 focus:ring-brand-purple/50 w-64"
                placeholder="Add description..."
                autoFocus
              />
            ) : (
              <p
                onClick={() => setEditingDesc(true)}
                className="text-sm text-th-text-muted mt-0.5 cursor-text hover:text-th-text transition-colors"
              >
                {template.description || 'Click to add description...'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Defaults Bar */}
      <div className="flex items-center gap-6 mb-6 bg-surface rounded-xl border border-th-border px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-th-text-muted">Default Margin %</label>
          <input
            type="number"
            step="0.01"
            className="bg-page border border-th-border rounded px-2 py-1 text-sm font-mono text-th-text w-20 text-right focus:outline-none focus:border-th-border-focus"
            value={marginValue}
            onChange={(e) => setMarginValue(e.target.value)}
            onBlur={(e) => handleDefaultChange('default_margin_pct', e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-th-text-muted">Default Waste %</label>
          <input
            type="number"
            step="0.01"
            className="bg-page border border-th-border rounded px-2 py-1 text-sm font-mono text-th-text w-20 text-right focus:outline-none focus:border-th-border-focus"
            value={wasteValue}
            onChange={(e) => setWasteValue(e.target.value)}
            onBlur={(e) => handleDefaultChange('default_waste_pct', e.target.value)}
          />
        </div>
        <div className="text-xs text-th-text-muted">
          {items.length} item{items.length !== 1 ? 's' : ''}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={() => setShowApplyModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface-hover rounded-lg transition-colors"
          >
            <FileText size={15} />
            Apply to Job
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
          >
            <Save size={15} />
            {saving ? 'Saving...' : 'Save Template'}
          </button>
        </div>
      </div>

      {/* Items Table */}
      <div className="bg-surface rounded-xl overflow-x-auto border border-th-border mb-4">
        <table className="w-full">
          <thead>
            <tr className="border-b border-th-border">
              <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Category</th>
              <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Description</th>
              <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Cost</th>
              <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">UOM</th>
              <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Margin%</th>
              <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Waste%</th>
              <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Measurement</th>
              <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Conv.</th>
              <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-2 py-2.5">Def Qty</th>
              <th className="w-8 px-2 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center text-th-text-muted text-sm py-8">
                  No items yet — click "Add Item" to get started
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <ItemRow
                  key={item.id}
                  item={item}
                  templateId={id}
                  onUpdate={fetchTemplate}
                  onDelete={setDeleteItemId}
                />
              ))
            )}
          </tbody>
        </table>

        <button
          onClick={() => setShowPicker(true)}
          className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-th-text-muted hover:text-brand-purple hover:bg-surface-hover/30 transition-colors border-t border-th-border"
        >
          <Plus size={14} />
          Add Item
        </button>
      </div>

      <MaterialPickerModal
        open={showPicker}
        onClose={() => setShowPicker(false)}
        onSelect={handleMaterialSelect}
        onAddManual={handleAddManual}
      />

      <ConfirmDialog
        isOpen={deleteItemId !== null}
        onConfirm={handleDeleteItem}
        onCancel={() => setDeleteItemId(null)}
        title="Delete Item"
        message="Remove this item from the template?"
        confirmLabel="Delete"
        variant="danger"
      />

      <ApplyToJobModal
        open={showApplyModal}
        onClose={() => setShowApplyModal(false)}
        templateId={id}
      />
    </div>
  )
}
