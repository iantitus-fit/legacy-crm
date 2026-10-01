import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Activity,
  Briefcase,
  Building2,
  Calculator,
  CalendarClock,
  CheckSquare,
  ChevronRight,
  DollarSign,
  FileText,
  FolderOpen,
  Info,
  MessageCircle,
  MessageSquare,
  Pencil,
  Plus,
  Receipt,
  Sparkles,
  Tag,
  Trash2,
  Zap,
} from 'lucide-react'
import { deleteContact, getContact, listContactTasks, updateContact } from '../api/contacts'
import { listContactDocuments } from '../api/documents'
import { listJobs } from '../api/jobs'
import { createEstimate, listEstimates } from '../api/estimates'
import { listInvoices } from '../api/invoices'
import { listPipelines } from '../api/pipeline'
import { listPipelineStages } from '../api/pipelineStages'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'
import ClientActivityTab from '../components/ClientActivityTab'
import FilesTab from '../components/FilesTab'
import ClientTasksTab from '../components/ClientTasksTab'
import NotesTab from '../components/NotesTab'
import SmsConversationView from '../components/SmsConversationView'
import ContactAutomationsTab from '../components/ContactAutomationsTab'
import BackButton from '../components/BackButton'
import PhoneLink from '../components/PhoneLink'
import AddressLink from '../components/AddressLink'
import JobPickerModal from '../components/JobPickerModal'
import AIPanelButton from '../components/AIPanelButton'

export default function ContactDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [contact, setContact] = useState(null)
  const [jobs, setJobs] = useState([])
  const [estimates, setEstimates] = useState([])
  const [invoices, setInvoices] = useState([])
  const [pipelines, setPipelines] = useState([])
  const [pipelineStages, setPipelineStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showDelete, setShowDelete] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [activeTab, setActiveTab] = useState('info')
  const [showJobPicker, setShowJobPicker] = useState(false)
  const [openTaskCount, setOpenTaskCount] = useState(0)
  const [documentCount, setDocumentCount] = useState(0)
  const [archivedExpanded, setArchivedExpanded] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([getContact(id), listPipelines().catch(() => ({ items: [] }))])
      .then(async ([data, pipelineData]) => {
        setContact(data)
        setForm(data)
        setPipelines(pipelineData.items || [])
        if (data.pipeline_id) {
          try {
            const stagesData = await listPipelineStages({ pipelineId: data.pipeline_id })
            setPipelineStages(stagesData.items || [])
          } catch {
            setPipelineStages([])
          }
        }
        const jobsData = await listJobs({ contactId: id, perPage: 50 })
        setJobs(jobsData.items)
        // Fetch estimates for all jobs owned by this contact
        const estimatePromises = jobsData.items.map((job) =>
          listEstimates({ jobId: job.id, perPage: 50 }).catch(() => ({ items: [] }))
        )
        const results = await Promise.all(estimatePromises)
        const allEstimates = results.flatMap((r, i) =>
          r.items.map((est) => ({
            ...est,
            job_address: jobsData.items[i].property_address || `Job #${jobsData.items[i].id}`,
          }))
        )
        setEstimates(allEstimates)

        // Fetch invoices — listInvoices only filters by estimate_id so
        // one call per estimate, then flatten.
        const invoicePromises = allEstimates.map((est) =>
          listInvoices({ estimateId: est.id, perPage: 50 }).catch(() => ({ items: [] }))
        )
        const invoiceResults = await Promise.all(invoicePromises)
        const allInvoices = invoiceResults.flatMap((r) => r.items || [])
        setInvoices(allInvoices)

        try {
          const taskList = await listContactTasks(id)
          setOpenTaskCount(taskList.filter((t) => t.status !== 'completed').length)
        } catch {
          setOpenTaskCount(0)
        }

        try {
          const docList = await listContactDocuments(id)
          setDocumentCount(docList.total ?? (docList.items?.length || 0))
        } catch {
          setDocumentCount(0)
        }
      })
      .catch(() => navigate('/contacts'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  // Find the contact's pipeline + stage for header badge display
  const pipelineInfo = (() => {
    if (!contact?.pipeline_id) return null
    const pipeline = pipelines.find((p) => p.id === contact.pipeline_id)
    if (!pipeline) return null
    const stage = pipelineStages.find((s) => s.id === contact.stage_id)
    return { pipeline, stage }
  })()

  // Summary metrics — Sprint 15b
  const JOB_STATUSES = new Set(["approved", "in_progress", "complete", "closed"])
  const contractValueTotal = estimates
    .filter((e) => JOB_STATUSES.has(e.status))
    .reduce((sum, e) => sum + Number(e.total || 0), 0)
  const activeEstimatesCount = estimates.filter(
    (e) => !["rejected", "closed"].includes(e.status)
  ).length
  const openInvoiceBalance = invoices.reduce(
    (sum, inv) => sum + Number(inv.balance || 0),
    0
  )
  const nextScheduled = estimates
    .filter((e) => e.scheduled_start && JOB_STATUSES.has(e.status))
    .map((e) => e.scheduled_start)
    .sort()[0]

  const formatCurrency = (value) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value || 0)

  // Sprint 15b — a "job" is an approved estimate
  const jobEstimates = estimates.filter((e) => JOB_STATUSES.has(e.status))

  // Sprint 15.6d — split estimates by archive state
  // Backend statuses (routers/estimates.py VALID_ESTIMATE_STATUSES). Everything
  // not rejected or closed is active, matching the summary count above.
  const ARCHIVED_ESTIMATE_STATUSES = new Set(['rejected', 'closed'])
  const activeEstimates = estimates.filter(
    (e) => !ARCHIVED_ESTIMATE_STATUSES.has(e.status)
  )
  const archivedEstimates = estimates.filter((e) =>
    ARCHIVED_ESTIMATE_STATUSES.has(e.status)
  )

  const handleCreateEstimateForJob = async (jobId) => {
    setShowJobPicker(false)
    try {
      const est = await createEstimate({ job_id: jobId, name: "" })
      addToast("Estimate created")
      navigate(`/estimates/${est.id}`)
    } catch (err) {
      addToast(err?.response?.data?.detail || "Failed to create estimate", "error")
    }
  }

  const handleSave = async () => {
    setError('')
    setSaving(true)
    try {
      const updated = await updateContact(id, {
        name: form.name,
        company: form.company || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        address: form.address || undefined,
        city: form.city || undefined,
        state: form.state || undefined,
        zip: form.zip || undefined,
        // Sprint 15b — client profile fields
        client_type: form.client_type || undefined,
        lead_source: form.lead_source || undefined,
      })
      setContact(updated)
      setEditing(false)
      addToast('Client profile updated')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update client profile')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleteError('')
    try {
      await deleteContact(id)
      addToast('Contact deleted')
      navigate('/contacts')
    } catch (err) {
      setDeleteError(
        err.response?.data?.detail || 'Failed to delete contact'
      )
      setShowDelete(false)
    }
  }

  const cancelEdit = () => {
    setForm(contact)
    setEditing(false)
    setError('')
  }

  if (loading) {
    return <LoadingSpinner centered />
  }

  if (!contact) return null

  const Field = ({ label, value, field, type = 'text', maxLength }) => {
    const renderView = () => {
      if (!value) return <span className="text-th-text-muted">—</span>
      if (type === 'tel') return <PhoneLink phone={value} className="text-th-text" />
      if (field === 'address') return <AddressLink address={value} className="text-th-text" />
      if (type === 'email')
        return (
          <a
            href={`mailto:${value}`}
            className="text-th-text hover:text-brand-purple transition-colors"
          >
            {value}
          </a>
        )
      return <span className="text-th-text">{value}</span>
    }
    return (
      <div>
        <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
          {label}
        </label>
        {editing && activeTab === 'info' ? (
          <input
            type={type}
            value={form[field] || ''}
            onChange={(e) => setForm({ ...form, [field]: e.target.value })}
            maxLength={maxLength}
            className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
          />
        ) : (
          <p className="text-sm">{renderView()}</p>
        )}
      </div>
    )
  }

  const EstimateRow = ({ est, muted = false }) => (
    <Link
      to={`/estimates/${est.id}`}
      className={`flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover/50 transition-colors ${
        muted ? 'opacity-60' : ''
      }`}
    >
      <div>
        <p className={`text-sm font-medium ${muted ? 'text-th-text-muted' : 'text-th-text'}`}>
          {est.name || `Estimate #${est.id}`}
        </p>
        <p className="text-xs text-th-text-muted mt-0.5">
          {est.job_address}
          {est.created_at && (
            <span className="ml-2">
              {new Date(est.created_at).toLocaleDateString()}
            </span>
          )}
        </p>
      </div>
      {est.total != null && (
        <span className={`text-sm font-mono ${muted ? 'text-th-text-muted' : 'text-brand-purple'}`}>
          {new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
          }).format(est.total)}
        </span>
      )}
    </Link>
  )

  const tabs = [
    { key: 'info', label: 'Info', icon: Info },
    { key: 'notes', label: 'Notes', icon: MessageSquare },
    { key: 'messages', label: 'Messages', icon: MessageCircle },
    { key: 'automations', label: 'Automations', icon: Zap },
    { key: 'tasks', label: 'Tasks', icon: CheckSquare, count: openTaskCount },
    { key: 'jobs', label: 'Jobs', icon: Briefcase, count: jobEstimates.length },
    { key: 'documents', label: 'Documents', icon: FolderOpen, count: documentCount },
    { key: 'estimates', label: 'Estimates', icon: Calculator, count: estimates.length },
    { key: 'invoices', label: 'Invoices', icon: Receipt, count: invoices.length },
    { key: 'activity', label: 'Activity', icon: Activity },
  ]

  return (
    <div>
      <BackButton to="/contacts" label="Back to Clients" />

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-th-text-muted mb-6">
        <Link to="/contacts" className="hover:text-th-text transition-colors">
          Clients
        </Link>
        <span>/</span>
        <span className="text-th-text">{contact.name}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col gap-4 mb-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold text-th-text break-words">{contact.name}</h1>
          {contact.company && (
            <div className="flex items-center gap-1.5 mt-1 text-sm text-th-text-secondary">
              <Building2 size={14} />
              <span>{contact.company}</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 mt-2">
            {contact.client_type && (
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                  contact.client_type === 'commercial'
                    ? 'bg-purple-500/20 text-purple-400'
                    : 'bg-blue-500/20 text-blue-400'
                }`}
              >
                {contact.client_type === 'commercial' ? 'Commercial' : 'Residential'}
              </span>
            )}
            {contact.lead_source && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-surface-hover text-th-text">
                <Tag size={11} />
                {contact.lead_source}
              </span>
            )}
            {pipelineInfo?.stage && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                style={{
                  backgroundColor: (pipelineInfo.stage.color || '#6B7280') + '33',
                  color: pipelineInfo.stage.color || '#9CA3AF',
                }}
                title={pipelineInfo.pipeline.name}
              >
                {pipelineInfo.stage.name}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-th-text-secondary">
            {contact.phone && <PhoneLink phone={contact.phone} className="text-th-text-secondary" />}
            {contact.email && (
              <a
                href={`mailto:${contact.email}`}
                className="hover:text-brand-purple transition-colors"
              >
                {contact.email}
              </a>
            )}
            {contact.address && (
              <AddressLink address={contact.address} className="text-th-text-secondary" />
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 lg:shrink-0">
          {editing ? (
            <>
              <button
                onClick={cancelEdit}
                className="px-3 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </>
          ) : (
            <>
              <AIPanelButton
                mode="entity"
                entityType="contact"
                entityId={Number(id)}
                label="Chat"
              />
              <button
                onClick={() => {
                  setActiveTab('info')
                  setEditing(true)
                }}
                className="flex items-center gap-2 px-3 py-2 text-sm text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover rounded-lg transition-colors"
              >
                <Pencil size={14} />
                Edit
              </button>
              <button
                onClick={() => setShowDelete(true)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:text-red-300 bg-surface hover:bg-surface-hover rounded-lg transition-colors"
              >
                <Trash2 size={14} />
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {(error || deleteError) && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error || deleteError}</p>
        </div>
      )}

      {/* Summary cards — Sprint 15b */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-th-text-muted uppercase tracking-wider">
              Contract Value
            </span>
            <DollarSign size={14} className="text-brand-purple" />
          </div>
          <p className="text-lg font-mono text-brand-purple font-semibold">
            {formatCurrency(contractValueTotal)}
          </p>
          <p className="text-[11px] text-th-text-muted mt-0.5">
            Approved estimates
          </p>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-th-text-muted uppercase tracking-wider">
              Active Estimates
            </span>
            <FileText size={14} className="text-blue-400" />
          </div>
          <p className="text-lg font-mono text-th-text font-semibold">
            {activeEstimatesCount}
          </p>
          <p className="text-[11px] text-th-text-muted mt-0.5">
            {estimates.length} total
          </p>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-th-text-muted uppercase tracking-wider">
              Open Balance
            </span>
            <Receipt size={14} className="text-red-400" />
          </div>
          <p
            className={`text-lg font-mono font-semibold ${
              openInvoiceBalance > 0 ? "text-red-400" : "text-th-text-secondary"
            }`}
          >
            {formatCurrency(openInvoiceBalance)}
          </p>
          <p className="text-[11px] text-th-text-muted mt-0.5">
            {invoices.length} invoice{invoices.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-th-text-muted uppercase tracking-wider">
              Next Scheduled
            </span>
            <CalendarClock size={14} className="text-emerald-400" />
          </div>
          {nextScheduled ? (
            <p className="text-sm font-mono text-th-text">
              {new Date(`${nextScheduled}T00:00:00`).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          ) : (
            <p className="text-sm text-th-text-muted">Not scheduled</p>
          )}
        </div>
      </div>

      {/* Tab Strip */}
      <div>
        <div className="flex border-b border-th-border mb-0">
          {tabs.map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === key
                  ? 'border-brand-purple text-brand-purple'
                  : 'border-transparent text-th-text-muted hover:text-th-text'
              }`}
            >
              <Icon size={16} />
              {label}
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  activeTab === key
                    ? 'bg-badge-warning-bg text-badge-warning-text'
                    : 'bg-surface-hover text-th-text-muted'
                }`}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="bg-surface rounded-b-xl rounded-tr-xl p-6">
          {activeTab === 'info' && (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                <Field label="Name" value={contact.name} field="name" />
                <Field label="Company" value={contact.company} field="company" />
                <div>
                  <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
                    Client Type
                  </label>
                  {editing ? (
                    <select
                      value={form.client_type || ''}
                      onChange={(e) => setForm({ ...form, client_type: e.target.value })}
                      className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    >
                      <option value="">—</option>
                      <option value="residential">Residential</option>
                      <option value="commercial">Commercial</option>
                    </select>
                  ) : (
                    <p className="text-sm">
                      {contact.client_type ? (
                        <span className="text-th-text capitalize">{contact.client_type}</span>
                      ) : (
                        <span className="text-th-text-muted">—</span>
                      )}
                    </p>
                  )}
                </div>
                <Field
                  label="Lead Source"
                  value={contact.lead_source}
                  field="lead_source"
                />
                <Field label="Email" value={contact.email} field="email" type="email" />
                <Field label="Phone" value={contact.phone} field="phone" type="tel" />
                <Field label="Address" value={contact.address} field="address" />
                <Field label="City" value={contact.city} field="city" />
                <div className="grid grid-cols-2 gap-4">
                  <Field label="State" value={contact.state} field="state" maxLength={2} />
                  <Field label="ZIP" value={contact.zip} field="zip" />
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-th-border">
                <p className="text-xs text-th-text-muted">
                  Created{' '}
                  <span className="font-mono">
                    {new Date(contact.created_at).toLocaleDateString()}
                  </span>
                </p>
              </div>
            </div>
          )}

          {activeTab === 'notes' && (
            <NotesTab entityType="contact" entityId={Number(id)} />
          )}

          {activeTab === 'messages' && (
            <SmsConversationView contactId={Number(id)} contact={contact} />
          )}

          {activeTab === 'automations' && (
            <ContactAutomationsTab
              contactId={Number(id)}
              contact={contact}
              onChanged={() => {
                // Re-fetch contact to pick up automations_enabled changes.
                getContact(id).then(setContact).catch(() => {})
              }}
            />
          )}

          {activeTab === 'tasks' && (
            <ClientTasksTab
              contactId={Number(id)}
              onTasksChange={setOpenTaskCount}
            />
          )}

          {activeTab === 'documents' && (
            <FilesTab
              entityType="contact"
              entityId={Number(id)}
              onCountChange={setDocumentCount}
            />
          )}

          {activeTab === 'activity' && (
            <ClientActivityTab contactId={Number(id)} />
          )}

          {activeTab === 'jobs' && (
            <div>
              {jobEstimates.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <Briefcase size={24} className="text-th-text-muted mb-2" />
                  <p className="text-th-text-muted text-sm">No active jobs</p>
                  <p className="text-xs text-th-text-muted mt-1">
                    Jobs appear here once an estimate is approved.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {jobEstimates.map((est) => (
                    <Link
                      key={est.id}
                      to={`/estimates/${est.id}`}
                      className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover/50 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-th-text truncate">
                          {est.name || `Estimate #${est.id}`}
                        </p>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-0.5 text-xs text-th-text-muted">
                          {est.job_type && (
                            <span className="capitalize">{est.job_type}</span>
                          )}
                          {est.crew_name && (
                            <span className="flex items-center gap-1">
                              <span
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: est.crew_color || '#6B7280' }}
                              />
                              {est.crew_name}
                            </span>
                          )}
                          {est.scheduled_start && (
                            <span>
                              {new Date(`${est.scheduled_start}T00:00:00`).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                              })}
                              {est.scheduled_end && est.scheduled_end !== est.scheduled_start && (
                                <>
                                  {' – '}
                                  {new Date(`${est.scheduled_end}T00:00:00`).toLocaleDateString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                  })}
                                </>
                              )}
                            </span>
                          )}
                          <span className="capitalize">{est.status?.replace('_', ' ')}</span>
                        </div>
                      </div>
                      {est.total != null && (
                        <span className="text-sm font-mono text-brand-purple shrink-0 ml-3">
                          {formatCurrency(est.total)}
                        </span>
                      )}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'estimates' && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-th-text-muted uppercase tracking-wider">
                  {estimates.length} estimate{estimates.length === 1 ? '' : 's'}
                </p>
                <button
                  onClick={() => setShowJobPicker(true)}
                  className="flex items-center gap-1.5 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-3 py-1.5 rounded text-xs transition-colors"
                >
                  <Plus size={14} />
                  Create Estimate
                </button>
              </div>
              {estimates.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <Calculator size={24} className="text-th-text-muted mb-2" />
                  <p className="text-th-text-muted text-sm">No estimates yet</p>
                </div>
              ) : (
                <>
                  {activeEstimates.length > 0 && (
                    <div className="mb-4">
                      <p className="text-[11px] font-medium text-th-text-muted uppercase tracking-wider mb-2">
                        Active Estimates
                      </p>
                      <div className="space-y-2">
                        {activeEstimates.map((est) => (
                          <EstimateRow key={est.id} est={est} />
                        ))}
                      </div>
                    </div>
                  )}

                  {archivedEstimates.length > 0 && (
                    <div className="border-t border-th-border pt-3">
                      <button
                        onClick={() => setArchivedExpanded((v) => !v)}
                        className="flex items-center gap-1.5 text-[11px] font-medium text-th-text-muted uppercase tracking-wider hover:text-th-text transition-colors w-full"
                      >
                        <ChevronRight
                          size={14}
                          className={`transition-transform ${
                            archivedExpanded ? 'rotate-90' : ''
                          }`}
                        />
                        Archived / Rejected ({archivedEstimates.length})
                      </button>
                      {archivedExpanded && (
                        <div className="space-y-2 mt-2">
                          {archivedEstimates.map((est) => (
                            <EstimateRow key={est.id} est={est} muted />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === 'invoices' && (
            <div>
              {invoices.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <Receipt size={24} className="text-th-text-muted mb-2" />
                  <p className="text-th-text-muted text-sm">No invoices yet</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-th-border text-[11px] text-th-text-muted uppercase tracking-wider">
                        <th className="text-left px-3 py-2 font-medium">Invoice</th>
                        <th className="text-left px-3 py-2 font-medium">Status</th>
                        <th className="text-right px-3 py-2 font-medium">Total</th>
                        <th className="text-right px-3 py-2 font-medium">Balance</th>
                        <th className="text-right px-3 py-2 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => {
                        const badgeClass =
                          inv.status === 'paid'
                            ? 'bg-green-500/20 text-green-400'
                            : inv.status === 'partial'
                            ? 'bg-amber-500/20 text-amber-400'
                            : inv.status === 'void'
                            ? 'bg-red-500/20 text-red-400'
                            : inv.status === 'sent'
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'bg-gray-500/20 text-th-text-secondary'
                        return (
                          <tr
                            key={inv.id}
                            onClick={() => navigate(`/invoices/${inv.id}`)}
                            className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                          >
                            <td className="px-3 py-2.5 text-sm font-mono text-th-text">
                              {inv.invoice_number}
                              {inv.is_deposit && (
                                <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400">
                                  Deposit
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2.5">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${badgeClass}`}>
                                {inv.status}
                              </span>
                            </td>
                            <td className="px-3 py-2.5 text-sm text-right font-mono text-th-text">
                              {formatCurrency(inv.total)}
                            </td>
                            <td className={`px-3 py-2.5 text-sm text-right font-mono ${
                              Number(inv.balance || 0) > 0 ? 'text-brand-purple' : 'text-th-text-muted'
                            }`}>
                              {formatCurrency(inv.balance)}
                            </td>
                            <td className="px-3 py-2.5 text-xs text-right text-th-text-muted font-mono">
                              {inv.date_invoiced
                                ? new Date(`${inv.date_invoiced}T00:00:00`).toLocaleDateString()
                                : '—'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={showDelete}
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
        title="Delete Client"
        message="This action cannot be undone. Are you sure you want to delete this client profile?"
        confirmLabel="Delete"
        variant="danger"
      />

      {showJobPicker && (
        <JobPickerModal
          title={`Select a Job for ${contact.name}`}
          contactId={Number(id)}
          onClose={() => setShowJobPicker(false)}
          onPick={handleCreateEstimateForJob}
        />
      )}

    </div>
  )
}
