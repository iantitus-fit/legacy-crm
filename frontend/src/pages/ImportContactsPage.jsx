import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  CloudUpload,
  Download,
  FileSpreadsheet,
  Loader2,
  Trash2,
  Undo2,
  Upload,
  Users,
} from 'lucide-react'
import {
  confirmImport,
  listImportHistory,
  previewImport,
  undoImport,
} from '../api/contactImport'
import { listPipelines } from '../api/pipeline'
import { listPipelineStages } from '../api/pipelineStages'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'

const TARGET_FIELDS = [
  { value: '', label: 'Skip this column' },
  { value: 'name', label: 'Name' },
  { value: 'first_name', label: 'First Name' },
  { value: 'last_name', label: 'Last Name' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'company', label: 'Company' },
  { value: 'address', label: 'Address' },
  { value: 'city', label: 'City' },
  { value: 'state', label: 'State' },
  { value: 'zip_code', label: 'ZIP Code' },
  { value: 'lead_source', label: 'Lead Source' },
  { value: 'client_type', label: 'Client Type' },
  { value: 'notes', label: 'Add to Notes' },
]

const STEP_LABELS = ['Upload', 'Map Fields', 'Preview & Options', 'Results']

export default function ImportContactsPage() {
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState(null)
  const [mappings, setMappings] = useState({})
  const [options, setOptions] = useState({
    default_client_type: 'residential',
    default_lead_source: 'CSV Import',
    duplicate_handling: 'skip',
    combine_unmapped_to_notes: true,
    pipeline_id: null,
    stage_id: null,
  })
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [pipelines, setPipelines] = useState([])
  const [stages, setStages] = useState([])
  const [confirmUndo, setConfirmUndo] = useState(null)
  const fileInputRef = useRef(null)

  const refreshHistory = async () => {
    setHistoryLoading(true)
    try {
      const data = await listImportHistory({ perPage: 20 })
      setHistory(data.items || [])
    } catch {
      setHistory([])
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    refreshHistory()
    listPipelines()
      .then((data) => setPipelines(data.items || []))
      .catch(() => setPipelines([]))
  }, [])

  useEffect(() => {
    if (!options.pipeline_id) {
      setStages([])
      return
    }
    listPipelineStages({ pipelineId: options.pipeline_id })
      .then((data) => setStages(data.items || []))
      .catch(() => setStages([]))
  }, [options.pipeline_id])

  const handleFile = (f) => {
    if (!f) return
    if (f.size > 50 * 1024 * 1024) {
      addToast('File too large (50MB max)', 'error')
      return
    }
    setFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      const data = await previewImport(file)
      setPreview(data)
      setMappings({ ...data.suggested_mappings })
      setStep(2)
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to parse file',
        'error'
      )
    } finally {
      setUploading(false)
    }
  }

  const handleMappingChange = (column, target) => {
    setMappings((prev) => ({ ...prev, [column]: target || null }))
  }

  const handleConfirmImport = async () => {
    setImporting(true)
    try {
      const data = await confirmImport({
        previewToken: preview.preview_token,
        fieldMappings: mappings,
        options,
      })
      setResult(data)
      setStep(4)
      refreshHistory()
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Import failed',
        'error'
      )
    } finally {
      setImporting(false)
    }
  }

  const handleUndo = async (importId) => {
    try {
      const data = await undoImport(importId)
      addToast(`Removed ${data.soft_deleted} contacts`)
      refreshHistory()
      if (result?.import_id === importId) {
        setResult({ ...result, undone: true })
      }
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Undo failed',
        'error'
      )
    } finally {
      setConfirmUndo(null)
    }
  }

  const reset = () => {
    setStep(1)
    setFile(null)
    setPreview(null)
    setMappings({})
    setResult(null)
  }

  const mappedTargetCount = (target) =>
    Object.values(mappings).filter((t) => t === target).length

  const hasNameMapping =
    mappedTargetCount('name') > 0 ||
    (mappedTargetCount('first_name') > 0 && mappedTargetCount('last_name') > 0)

  const previewTableColumns = preview
    ? Object.entries(mappings)
        .filter(([, t]) => t)
        .map(([col, t]) => ({ col, target: t }))
    : []

  const importableEstimate = preview
    ? preview.sample_rows.length > 0
      ? Math.max(0, preview.importable_rows)
      : 0
    : 0

  return (
    <div className="max-w-6xl mx-auto pb-12">
      <div className="flex items-center gap-3 mb-2 text-sm text-th-text-muted">
        <Link to="/contacts" className="hover:text-th-text transition-colors flex items-center gap-1">
          <ArrowLeft size={14} /> Back to Clients
        </Link>
      </div>
      <h1 className="text-2xl font-bold text-th-text mb-1">Import Contacts</h1>
      <p className="text-sm text-th-text-secondary mb-6">
        Bring data in from AccuLynx, DripJobs, Salesforce, or any CSV/XLSX export.
      </p>

      {/* Stepper */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        {STEP_LABELS.map((label, i) => {
          const idx = i + 1
          const active = step === idx
          const done = step > idx
          return (
            <div key={label} className="flex items-center gap-2">
              <span
                className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold ${
                  done
                    ? 'bg-brand-purple text-white'
                    : active
                    ? 'bg-brand-purple/20 text-brand-purple border border-brand-purple'
                    : 'bg-surface-hover text-th-text-muted'
                }`}
              >
                {idx}
              </span>
              <span
                className={
                  active
                    ? 'text-th-text font-medium'
                    : done
                    ? 'text-th-text-secondary'
                    : 'text-th-text-muted'
                }
              >
                {label}
              </span>
              {idx < STEP_LABELS.length && (
                <ChevronRight size={14} className="text-th-text-muted" />
              )}
            </div>
          )
        })}
      </div>

      {step === 1 && (
        <div className="bg-surface rounded-xl border border-th-border p-8">
          <div
            className="border-2 border-dashed border-th-border-secondary rounded-xl p-10 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0])
            }}
          >
            <CloudUpload size={36} className="mx-auto text-th-text-muted mb-3" />
            <p className="text-th-text font-medium mb-1">
              Drag a CSV or XLSX file here
            </p>
            <p className="text-xs text-th-text-muted mb-4">
              or click to browse · 50MB max
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => handleFile(e.target.files?.[0])}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="bg-surface-hover hover:bg-surface-hover/70 text-th-text px-4 py-2 rounded-lg text-sm transition-colors"
            >
              Choose File
            </button>
            {file && (
              <div className="mt-4 inline-flex items-center gap-2 bg-surface-hover px-3 py-2 rounded-lg text-sm">
                <FileSpreadsheet size={16} className="text-brand-purple" />
                <span className="text-th-text">{file.name}</span>
                <span className="text-th-text-muted">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            )}
          </div>
          <div className="flex justify-end mt-6">
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {uploading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Upload size={16} />
              )}
              Upload &amp; Preview
            </button>
          </div>

          {/* Import history */}
          <div className="mt-10">
            <h2 className="text-sm font-semibold text-th-text mb-3">
              Recent Imports
            </h2>
            {historyLoading ? (
              <p className="text-xs text-th-text-muted">Loading…</p>
            ) : history.length === 0 ? (
              <p className="text-xs text-th-text-muted">
                No imports yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-th-border text-[11px] text-th-text-muted uppercase tracking-wider">
                      <th className="text-left px-3 py-2 font-medium">File</th>
                      <th className="text-left px-3 py-2 font-medium">User</th>
                      <th className="text-right px-3 py-2 font-medium">Imported</th>
                      <th className="text-right px-3 py-2 font-medium">Skipped</th>
                      <th className="text-right px-3 py-2 font-medium">Duration</th>
                      <th className="text-right px-3 py-2 font-medium">When</th>
                      <th className="text-right px-3 py-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((row) => (
                      <tr
                        key={row.import_id}
                        className="border-b border-th-border/50 last:border-0"
                      >
                        <td className="px-3 py-2.5 text-th-text">{row.file_name}</td>
                        <td className="px-3 py-2.5 text-th-text-secondary">
                          {row.user_name || '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text">
                          {row.imported_count}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text-muted">
                          {row.skipped_count + row.duplicate_count}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono text-th-text-muted">
                          {row.duration_seconds != null
                            ? `${row.duration_seconds.toFixed(1)}s`
                            : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right text-th-text-muted text-xs">
                          {new Date(row.created_at).toLocaleString()}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {row.undone_at ? (
                            <span className="text-xs text-th-text-muted">Undone</span>
                          ) : (
                            <div className="inline-flex items-center gap-2">
                              <button
                                onClick={() =>
                                  navigate(
                                    `/contacts?import_id=${row.import_id}`
                                  )
                                }
                                className="text-xs text-brand-purple hover:underline"
                              >
                                View
                              </button>
                              <button
                                onClick={() => setConfirmUndo(row)}
                                className="text-xs text-red-400 hover:underline flex items-center gap-1"
                              >
                                <Undo2 size={12} /> Undo
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {step === 2 && preview && (
        <div className="bg-surface rounded-xl border border-th-border p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-th-text">Map Fields</h2>
              <p className="text-xs text-th-text-muted mt-1">
                {preview.columns_detected.length} columns detected ·{' '}
                {preview.total_rows} rows
              </p>
            </div>
            <button
              onClick={reset}
              className="text-xs text-th-text-muted hover:text-th-text"
            >
              Cancel
            </button>
          </div>

          {!hasNameMapping && (
            <div className="flex items-center gap-2 bg-amber-500/10 text-amber-400 text-sm rounded-lg px-3 py-2 mb-4">
              <AlertTriangle size={16} />
              No "Name" column mapped — rows without a name will be skipped.
            </div>
          )}

          {mappedTargetCount('first_name') > 0 &&
            mappedTargetCount('last_name') > 0 && (
              <div className="flex items-center gap-2 bg-brand-purple/10 text-brand-purple text-sm rounded-lg px-3 py-2 mb-4">
                <CheckCircle2 size={16} />
                First Name + Last Name will be combined into a single Name field.
              </div>
            )}

          <div className="space-y-2">
            {preview.columns_detected.map((col) => {
              const sample = preview.sample_rows[0]?.[col] || ''
              return (
                <div
                  key={col}
                  className="grid grid-cols-12 gap-3 items-center bg-surface-hover/40 rounded-lg p-3"
                >
                  <div className="col-span-5">
                    <p className="text-sm font-medium text-th-text">{col}</p>
                    <p className="text-xs text-th-text-muted truncate">
                      {sample || <span className="italic">empty</span>}
                    </p>
                  </div>
                  <div className="col-span-1 text-th-text-muted text-center">
                    →
                  </div>
                  <div className="col-span-6">
                    <select
                      value={mappings[col] || ''}
                      onChange={(e) => handleMappingChange(col, e.target.value)}
                      className="w-full bg-surface border border-th-border-secondary rounded-lg px-3 py-1.5 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
                    >
                      {TARGET_FIELDS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex justify-end gap-2 mt-6">
            <button
              onClick={() => setStep(1)}
              className="text-sm px-4 py-2 rounded-lg hover:bg-surface-hover text-th-text-secondary"
            >
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!hasNameMapping}
              className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              Continue to Preview
            </button>
          </div>
        </div>
      )}

      {step === 3 && preview && (
        <div className="bg-surface rounded-xl border border-th-border p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-th-text">
                Preview &amp; Options
              </h2>
              <p className="text-xs text-th-text-muted mt-1">
                Review the data, set defaults, then import.
              </p>
            </div>
            <button
              onClick={reset}
              className="text-xs text-th-text-muted hover:text-th-text"
            >
              Cancel
            </button>
          </div>

          {/* Stats bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <Stat label="Total Rows" value={preview.total_rows} />
            <Stat label="Importable" value={preview.importable_rows} accent />
            <Stat
              label="Duplicates"
              value={preview.potential_duplicates}
              warn={preview.potential_duplicates > 0}
            />
            <Stat
              label="Skipped"
              value={preview.skipped_rows}
              warn={preview.skipped_rows > 0}
            />
          </div>

          {/* Sample table */}
          <div className="overflow-x-auto mb-5 border border-th-border rounded-lg">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-surface-hover/50 text-th-text-muted uppercase tracking-wider">
                  {previewTableColumns.map(({ col, target }) => (
                    <th
                      key={col}
                      className="text-left px-3 py-2 font-medium whitespace-nowrap"
                    >
                      {target}
                      <span className="block normal-case text-[10px] text-th-text-muted/70">
                        from {col}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.sample_rows.map((row, i) => (
                  <tr key={i} className="border-t border-th-border/40">
                    {previewTableColumns.map(({ col }) => (
                      <td
                        key={col}
                        className="px-3 py-1.5 text-th-text whitespace-nowrap"
                      >
                        {row[col] || (
                          <span className="text-th-text-muted">—</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Options */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <Field label="Default client type">
              <select
                value={options.default_client_type || ''}
                onChange={(e) =>
                  setOptions({ ...options, default_client_type: e.target.value || null })
                }
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text"
              >
                <option value="">— None —</option>
                <option value="residential">Residential</option>
                <option value="commercial">Commercial</option>
              </select>
            </Field>
            <Field label="Default lead source">
              <input
                type="text"
                value={options.default_lead_source || ''}
                onChange={(e) =>
                  setOptions({ ...options, default_lead_source: e.target.value })
                }
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text"
              />
            </Field>
            <Field label="Duplicate handling">
              <div className="flex gap-2 text-sm">
                {[
                  { value: 'skip', label: 'Skip duplicates' },
                  { value: 'import', label: 'Import all' },
                ].map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex-1 cursor-pointer rounded-lg px-3 py-2 border ${
                      options.duplicate_handling === opt.value
                        ? 'border-brand-purple bg-brand-purple/10 text-th-text'
                        : 'border-th-border-secondary text-th-text-secondary'
                    }`}
                  >
                    <input
                      type="radio"
                      name="dup"
                      value={opt.value}
                      checked={options.duplicate_handling === opt.value}
                      onChange={(e) =>
                        setOptions({
                          ...options,
                          duplicate_handling: e.target.value,
                        })
                      }
                      className="hidden"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Combine unmapped columns into Notes">
              <label className="flex items-center gap-2 text-sm text-th-text">
                <input
                  type="checkbox"
                  checked={options.combine_unmapped_to_notes}
                  onChange={(e) =>
                    setOptions({
                      ...options,
                      combine_unmapped_to_notes: e.target.checked,
                    })
                  }
                  className="rounded border-th-border-secondary"
                />
                Yes, preserve as a note on each contact
              </label>
            </Field>
            <Field label="Place in pipeline (optional)">
              <select
                value={options.pipeline_id || ''}
                onChange={(e) =>
                  setOptions({
                    ...options,
                    pipeline_id: e.target.value
                      ? Number(e.target.value)
                      : null,
                    stage_id: null,
                  })
                }
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text"
              >
                <option value="">— None —</option>
                {pipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            {options.pipeline_id && (
              <Field label="Stage">
                <select
                  value={options.stage_id || ''}
                  onChange={(e) =>
                    setOptions({
                      ...options,
                      stage_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text"
                >
                  <option value="">— First stage —</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={() => setStep(2)}
              className="text-sm px-4 py-2 rounded-lg hover:bg-surface-hover text-th-text-secondary"
            >
              Back
            </button>
            <button
              onClick={handleConfirmImport}
              disabled={importing || preview.importable_rows === 0}
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-5 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {importing ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Download size={16} />
              )}
              Import {preview.importable_rows.toLocaleString()} Contacts
            </button>
          </div>
        </div>
      )}

      {step === 4 && result && (
        <div className="bg-surface rounded-xl border border-th-border p-8">
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle2 size={28} className="text-green-400" />
            <h2 className="text-xl font-semibold text-th-text">
              {result.undone
                ? 'Import undone'
                : `Imported ${result.imported.toLocaleString()} contacts`}
            </h2>
          </div>
          {!result.undone && (
            <p className="text-sm text-th-text-secondary mb-6">
              Finished in {result.duration_seconds.toFixed(1)} seconds.
            </p>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Stat label="Imported" value={result.imported} accent />
            <Stat
              label="Duplicates Skipped"
              value={result.skipped_duplicates}
            />
            <Stat label="Invalid Skipped" value={result.skipped_invalid} />
            <Stat label="Total Processed" value={result.total_processed} />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() =>
                navigate(`/contacts?import_id=${result.import_id}`)
              }
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              <Users size={16} /> View Imported Contacts
            </button>
            {!result.undone && (
              <button
                onClick={() =>
                  setConfirmUndo({
                    import_id: result.import_id,
                    file_name: file?.name,
                    imported_count: result.imported,
                  })
                }
                className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2 rounded-lg text-sm transition-colors"
              >
                <Trash2 size={16} /> Undo Import
              </button>
            )}
            <button
              onClick={reset}
              className="text-sm px-4 py-2 rounded-lg hover:bg-surface-hover text-th-text-secondary"
            >
              Start Another Import
            </button>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={Boolean(confirmUndo)}
        onConfirm={() => confirmUndo && handleUndo(confirmUndo.import_id)}
        onCancel={() => setConfirmUndo(null)}
        title="Undo this import?"
        message={
          confirmUndo
            ? `This will remove all ${
                confirmUndo.imported_count ?? ''
              } contacts from ${confirmUndo.file_name || 'this import'}. Are you sure?`
            : ''
        }
        confirmLabel="Undo Import"
        variant="danger"
      />
    </div>
  )
}

function Stat({ label, value, accent = false, warn = false }) {
  return (
    <div className="bg-surface-hover/50 rounded-lg p-3">
      <p className="text-[11px] uppercase tracking-wider text-th-text-muted">
        {label}
      </p>
      <p
        className={`text-xl font-mono ${
          accent
            ? 'text-brand-purple'
            : warn
            ? 'text-amber-400'
            : 'text-th-text'
        }`}
      >
        {Number(value || 0).toLocaleString()}
      </p>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-1">
        {label}
      </label>
      {children}
    </div>
  )
}
