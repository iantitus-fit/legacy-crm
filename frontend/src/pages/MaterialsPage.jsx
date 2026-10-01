import { useEffect, useState } from 'react'
import { Package, Upload, AlertTriangle, X, Pencil, Check } from 'lucide-react'
import { listMaterials, listCategories, updateMaterial, deleteMaterial, importMaterials } from '../api/materials'
import { listPriceLists, updatePriceList } from '../api/priceLists'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'

const formatCurrency = (value) => {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

function PriceListCards({ priceLists, onUpdate }) {
  const today = new Date().toISOString().slice(0, 10)

  const getStatus = (pl) => {
    if (!pl.expiration_date) return { label: 'No expiry set', color: 'text-th-text-muted' }
    if (pl.expiration_date < today) return { label: 'Expired', color: 'text-red-400' }
    const exp = new Date(pl.expiration_date)
    const thirtyDays = new Date()
    thirtyDays.setDate(thirtyDays.getDate() + 30)
    if (exp <= thirtyDays) return { label: 'Expiring soon', color: 'text-brand-purple-text' }
    return { label: 'Current', color: 'text-emerald-400' }
  }

  const [editingId, setEditingId] = useState(null)
  const [editDate, setEditDate] = useState('')

  const handleSave = async (id) => {
    await onUpdate(id, { expiration_date: editDate || null })
    setEditingId(null)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {priceLists.map((pl) => {
        const status = getStatus(pl)
        return (
          <div key={pl.id} className="bg-surface rounded-xl p-4 border border-th-border">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-th-text">{pl.name}</h3>
              <span className={`text-xs font-medium ${status.color}`}>{status.label}</span>
            </div>
            <p className="text-2xl font-mono font-bold text-th-text mb-1">
              {pl.material_count.toLocaleString()}
            </p>
            <p className="text-xs text-th-text-muted mb-2">materials</p>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-th-text-muted">Expires:</span>
              {editingId === pl.id ? (
                <span className="flex items-center gap-1">
                  <input
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    className="bg-page border border-th-border-secondary rounded px-2 py-0.5 text-xs text-th-text"
                  />
                  <button onClick={() => handleSave(pl.id)} className="text-emerald-400 hover:text-emerald-300">
                    <Check size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-th-text-muted hover:text-th-text">
                    <X size={14} />
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => { setEditingId(pl.id); setEditDate(pl.expiration_date || '') }}
                  className="text-th-text hover:text-brand-purple-text flex items-center gap-1"
                >
                  {pl.expiration_date || 'Not set'}
                  <Pencil size={10} />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ImportModal({ open, onClose, onSuccess }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const { addToast } = useToast()

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    try {
      const res = await importMaterials(file)
      setResult(res)
      if (res.errors.length === 0) {
        addToast(`Imported ${res.materials_imported} materials from ${res.price_lists_created} price list(s)`)
        onSuccess()
      }
    } catch (err) {
      addToast(err.response?.data?.detail || 'Import failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">Import Materials CSV</h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text"><X size={20} /></button>
        </div>

        {result ? (
          <div className="space-y-3">
            <p className="text-emerald-400 font-medium">
              Imported {result.materials_imported} materials from {result.price_lists_created} price list(s)
            </p>
            {result.errors.length > 0 && (
              <div className="bg-red-900/20 border border-red-800 rounded-lg p-3">
                <p className="text-red-400 text-sm font-medium mb-1">{result.errors.length} error(s):</p>
                <ul className="text-xs text-red-300 space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <button onClick={onClose} className="w-full bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded-lg py-2 transition-colors">
              Done
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-th-text-secondary">
              Upload a CSV with columns: item_number, description, unit_price, uom, category, source, ocr_flag
            </p>
            <div className="border-2 border-dashed border-th-border-secondary rounded-lg p-6 text-center">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files[0])}
                className="hidden"
                id="csv-upload"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <Upload size={32} className="mx-auto text-th-text-muted mb-2" />
                <p className="text-sm text-th-text">{file ? file.name : 'Click to select CSV file'}</p>
              </label>
            </div>
            <button
              onClick={handleImport}
              disabled={!file || loading}
              className="w-full bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 disabled:cursor-not-allowed text-btn-primary-text font-semibold rounded-lg py-2 transition-colors"
            >
              {loading ? 'Importing...' : 'Import'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function EditMaterialModal({ material, open, onClose, onSave }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    if (material) {
      setForm({
        item_number: material.item_number,
        description: material.description,
        unit_price: material.unit_price,
        uom: material.uom || '',
        category: material.category,
        ocr_flag: material.ocr_flag || '',
      })
    }
  }, [material])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        ...form,
        ocr_flag: form.ocr_flag || null,
        uom: form.uom || null,
      }
      await onSave(material.id, payload)
      onClose()
      addToast('Material updated')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Update failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!open || !material) return null

  const inputClass = 'w-full bg-page border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">Edit Material</h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Item Number</label>
              <input className={inputClass} value={form.item_number || ''} onChange={(e) => setForm({ ...form, item_number: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">UOM</label>
              <input className={inputClass} value={form.uom || ''} onChange={(e) => setForm({ ...form, uom: e.target.value })} placeholder="SQ, BD, BX, PC, RL" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Description</label>
            <input className={inputClass} value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Unit Price</label>
              <input type="number" step="0.01" className={inputClass} value={form.unit_price || ''} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Category</label>
              <input className={inputClass} value={form.category || ''} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </div>
          </div>
          {material.ocr_flag && (
            <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle size={14} className="text-brand-purple-text" />
                <span className="text-xs font-medium text-brand-purple-text">OCR Flag</span>
              </div>
              <p className="text-xs text-amber-300 mb-2">{material.ocr_flag}</p>
              <button
                type="button"
                onClick={() => setForm({ ...form, ocr_flag: '' })}
                className="text-xs text-brand-purple-text hover:text-amber-300 underline"
              >
                Mark as reviewed (clear flag)
              </button>
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 bg-surface-hover hover:bg-th-border-secondary text-th-text rounded-lg py-2 text-sm transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="flex-1 bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text font-semibold rounded-lg py-2 text-sm transition-colors">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function MaterialsPage() {
  const [materials, setMaterials] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [priceListId, setPriceListId] = useState('')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState([])
  const [priceLists, setPriceLists] = useState([])
  const [showImport, setShowImport] = useState(false)
  const [editingMaterial, setEditingMaterial] = useState(null)
  const { addToast } = useToast()
  const perPage = 50

  const fetchMaterials = () => {
    setLoading(true)
    listMaterials({
      search,
      category: category || undefined,
      priceListId: priceListId || undefined,
      flagged: flaggedOnly || undefined,
      page,
      perPage,
    })
      .then((data) => {
        setMaterials(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load materials', 'error'))
      .finally(() => setLoading(false))
  }

  const fetchMeta = () => {
    listCategories().then(setCategories).catch(() => {})
    listPriceLists().then((d) => setPriceLists(d.items)).catch(() => {})
  }

  useEffect(() => {
    fetchMeta()
  }, [])

  useEffect(() => {
    fetchMaterials()
  }, [search, category, priceListId, flaggedOnly, page])

  const handleSearch = (value) => {
    setSearch(value)
    setPage(1)
  }

  const handleFilterChange = (setter) => (e) => {
    setter(e.target.value)
    setPage(1)
  }

  const handleUpdate = async (id, data) => {
    const updated = await updateMaterial(id, data)
    setMaterials((prev) => prev.map((m) => (m.id === id ? updated : m)))
    return updated
  }

  const handleDeactivate = async (id) => {
    await deleteMaterial(id)
    setMaterials((prev) => prev.filter((m) => m.id !== id))
    setTotal((t) => t - 1)
    addToast('Material deactivated')
  }

  const handlePriceListUpdate = async (id, data) => {
    await updatePriceList(id, data)
    fetchMeta()
  }

  const selectClass = 'bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus'

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-th-text">Materials Library</h1>
          <p className="text-sm text-th-text-muted mt-1">
            {total.toLocaleString()} materials across {priceLists.length} price list{priceLists.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowImport(true)}
          className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded-lg px-4 py-2.5 text-sm transition-colors"
        >
          <Upload size={16} />
          Import CSV
        </button>
      </div>

      {/* Price List Cards */}
      {priceLists.length > 0 && (
        <PriceListCards priceLists={priceLists} onUpdate={handlePriceListUpdate} />
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex-1 min-w-[200px] max-w-sm">
          <SearchInput
            value={search}
            onChange={handleSearch}
            placeholder="Search by item # or description..."
          />
        </div>
        <select
          value={category}
          onChange={handleFilterChange(setCategory)}
          className={selectClass}
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.category} value={c.category}>
              {c.category} ({c.count})
            </option>
          ))}
        </select>
        <select
          value={priceListId}
          onChange={handleFilterChange(setPriceListId)}
          className={selectClass}
        >
          <option value="">All Sources</option>
          {priceLists.map((pl) => (
            <option key={pl.id} value={pl.id}>
              {pl.name} ({pl.material_count})
            </option>
          ))}
        </select>
        <button
          onClick={() => { setFlaggedOnly(!flaggedOnly); setPage(1) }}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border transition-colors ${
            flaggedOnly
              ? 'bg-badge-warning-bg border-brand-purple text-brand-purple-text'
              : 'bg-page border-th-border text-th-text-secondary hover:text-th-text'
          }`}
        >
          <AlertTriangle size={14} />
          Needs Review
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : materials.length === 0 ? (
        <EmptyState
          icon={Package}
          title={search || category || flaggedOnly ? 'No materials found' : 'No materials yet'}
          description={
            search || category || flaggedOnly
              ? 'Try adjusting your filters'
              : 'Import a CSV to get started'
          }
        />
      ) : (
        <>
          <div className="bg-surface rounded-xl overflow-x-auto border border-th-border">
            <table className="w-full">
              <thead>
                <tr className="border-b border-th-border">
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Item #</th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Description</th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Unit Price</th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">UOM</th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Category</th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Source</th>
                  <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Status</th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-th-border">
                {materials.map((mat) => (
                  <tr key={mat.id} className="hover:bg-surface-hover/30 transition-colors">
                    <td className="px-4 py-3 text-sm font-mono text-th-text">{mat.item_number}</td>
                    <td className="px-4 py-3 text-sm text-th-text max-w-xs truncate">{mat.description}</td>
                    <td className="px-4 py-3 text-sm font-mono text-th-text text-right">{formatCurrency(mat.unit_price)}</td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">{mat.uom || <span className="text-brand-purple text-xs">Missing</span>}</td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">{mat.category}</td>
                    <td className="px-4 py-3 text-sm text-th-text-muted">{mat.price_list_name}</td>
                    <td className="px-4 py-3 text-center">
                      {mat.ocr_flag ? (
                        <span className="inline-flex items-center gap-1 text-xs text-brand-purple-text" title={mat.ocr_flag}>
                          <AlertTriangle size={12} />
                          Review
                        </span>
                      ) : (
                        <span className="text-xs text-emerald-400">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setEditingMaterial(mat)}
                        className="text-th-text-muted hover:text-brand-purple-text transition-colors p-1"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
          />
        </>
      )}

      {/* Modals */}
      <ImportModal
        open={showImport}
        onClose={() => { setShowImport(false) }}
        onSuccess={() => { setShowImport(false); fetchMaterials(); fetchMeta() }}
      />
      <EditMaterialModal
        material={editingMaterial}
        open={!!editingMaterial}
        onClose={() => setEditingMaterial(null)}
        onSave={handleUpdate}
      />
    </div>
  )
}
