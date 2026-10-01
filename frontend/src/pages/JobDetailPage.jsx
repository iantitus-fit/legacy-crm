/**
 * DEPRECATED (Sprint 15 restructure): JobDetailPage is a legacy page.
 * In the new model, a "job" is an approved estimate. Users should
 * navigate to the Client Profile page (/contacts/:id) or the Estimate
 * Detail page (/estimates/:id) instead.
 *
 * This page is kept as a fallback for old bookmarks and deep links.
 * Remove it once the restructure is fully verified in production and
 * the jobs table is dropped.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Calculator,
  CalendarClock,
  CheckSquare,
  ChevronDown,
  Clock,
  DollarSign,
  FileText,
  Info,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Trash2,
  Users2,
} from 'lucide-react'
import { deleteJob, getJob, updateJob } from '../api/jobs'
import { getContact } from '../api/contacts'
import { getPipeline } from '../api/pipeline'
import { listEstimates } from '../api/estimates'
import { listTasks } from '../api/tasks'
import { listDocuments } from '../api/documents'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'
import QuickScheduleModal from '../components/QuickScheduleModal'
import LoadingSpinner from '../components/LoadingSpinner'
import JobEstimatesTab from '../components/JobEstimatesTab'
import JobTasksTab from '../components/JobTasksTab'
import FilesTab from '../components/FilesTab'
import NotesTab from '../components/NotesTab'
import BackButton from '../components/BackButton'
import PhoneLink from '../components/PhoneLink'
import AddressLink from '../components/AddressLink'

const JOB_TYPES = ['roof', 'gutter', 'siding', 'window']
const WORK_TYPES = ['insurance', 'retail']

export default function JobDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [job, setJob] = useState(null)
  const [contact, setContact] = useState(null)
  const [stages, setStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showDelete, setShowDelete] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [activeTab, setActiveTab] = useState('details')
  const [estimates, setEstimates] = useState([])
  const [tasks, setTasks] = useState([])
  const [documentCount, setDocumentCount] = useState(0)
  const [showOverflow, setShowOverflow] = useState(false)

  const fetchTabData = (jobId) => {
    listEstimates({ jobId }).then((d) => setEstimates(d.items)).catch(() => addToast('Failed to load estimates', 'error'))
    listTasks({ jobId }).then((d) => setTasks(d.items)).catch(() => addToast('Failed to load tasks', 'error'))
    listDocuments(jobId).then((d) => setDocumentCount(d.total ?? d.items.length)).catch(() => setDocumentCount(0))
  }

  useEffect(() => {
    setLoading(true)
    getJob(id)
      .then(async (jobData) => {
        setJob(jobData)
        setForm(jobData)
        fetchTabData(id)
        if (jobData.pipeline_id) {
          try {
            const pipelineData = await getPipeline(jobData.pipeline_id)
            const sorted = [...pipelineData.stages].sort((a, b) => a.sort_order - b.sort_order)
            setStages(sorted)
          } catch {
            // fall back to empty
          }
        }
        if (jobData.contact_id) {
          getContact(jobData.contact_id)
            .then(setContact)
            .catch(() => {})
        }
      })
      .catch(() => navigate('/jobs'))
      .finally(() => setLoading(false))
  }, [id, navigate])

  const handleSave = async () => {
    setError('')
    setSaving(true)
    try {
      const updated = await updateJob(id, {
        stage_id: form.stage_id ? Number(form.stage_id) : undefined,
        job_type: form.job_type || undefined,
        work_type: form.work_type || undefined,
        property_address: form.property_address || undefined,
        contract_value: form.contract_value || undefined,
        notes: form.notes || undefined,
        lead_source: form.lead_source || undefined,
      })
      setJob(updated)
      setForm(updated)
      setEditing(false)
      addToast('Job updated')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update job')
    } finally {
      setSaving(false)
    }
  }

  const handleStageChange = async (newStageId) => {
    try {
      const updated = await updateJob(id, { stage_id: Number(newStageId) })
      setJob(updated)
      setForm(updated)
      addToast('Stage updated')
    } catch {
      addToast('Failed to update stage', 'error')
    }
  }

  const handleDelete = async () => {
    setDeleteError('')
    try {
      await deleteJob(id)
      addToast('Job deleted')
      navigate('/jobs')
    } catch (err) {
      setDeleteError(err.response?.data?.detail || 'Failed to delete job')
      setShowDelete(false)
    }
  }

  const cancelEdit = () => {
    setForm(job)
    setEditing(false)
    setError('')
  }

  const formatCurrency = (value) => {
    if (!value) return '-'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value)
  }

  if (loading) {
    return <LoadingSpinner centered />
  }

  if (!job) return null

  const currentStage = stages.find((s) => s.id === job.stage_id)

  const tabs = [
    { key: 'details', label: 'Details', icon: Info },
    { key: 'notes', label: 'Notes', icon: MessageSquare },
    { key: 'estimates', label: 'Estimates', icon: Calculator, count: estimates.length },
    { key: 'tasks', label: 'Tasks', icon: CheckSquare, count: tasks.length },
    { key: 'documents', label: 'Files', icon: FileText, count: documentCount },
    { key: 'activity', label: 'Activity', icon: Clock },
  ]

  return (
    <div>
      <BackButton to="/jobs" label="Back to Jobs" />

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-th-text-muted mb-4">
        <Link to="/jobs" className="hover:text-th-text transition-colors">
          Jobs
        </Link>
        <span>/</span>
        <span className="text-th-text">
          {job.display_name || job.property_address || `Job #${job.id}`}
        </span>
      </div>

      {/* Enhanced Header */}
      <div className="flex flex-col gap-4 mb-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-th-text break-words">
            {job.display_name || job.property_address || `Job #${job.id}`}
          </h1>
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            {contact && (
              <Link
                to={`/contacts/${contact.id}`}
                className="text-brand-purple hover:text-brand-purple-text text-sm font-medium transition-colors"
              >
                {contact.name}
              </Link>
            )}
            {currentStage && (
              <span
                className="text-xs px-2 py-0.5 rounded font-medium"
                style={{
                  backgroundColor: (currentStage.color || '#6B7280') + '33',
                  color: currentStage.color || '#9CA3AF',
                }}
              >
                {currentStage.name}
              </span>
            )}
            {job.work_type && (
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${
                  job.work_type === 'insurance'
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-emerald-500/20 text-emerald-400'
                }`}
              >
                {job.work_type.charAt(0).toUpperCase() + job.work_type.slice(1)}
              </span>
            )}
            {job.lead_source && (
              <span className="text-xs text-th-text-muted">
                via {job.lead_source}
              </span>
            )}
            {job.assigned_to_name && (
              <span className="text-xs text-th-text-secondary">
                Assigned to {job.assigned_to_name}
              </span>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-wrap items-center gap-2 lg:shrink-0 lg:justify-end">
          {/* Stage change dropdown */}
          <select
            value={job.stage_id || ''}
            onChange={(e) => handleStageChange(e.target.value)}
            className="flex-1 min-w-[8rem] lg:flex-none bg-surface border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
          >
            {stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setShowSchedule(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover rounded-lg transition-colors border border-th-border-secondary"
          >
            <CalendarClock size={14} />
            {job.scheduled_date ? 'Reschedule' : 'Schedule'}
          </button>

          <button
            onClick={() => {
              setActiveTab('details')
              setEditing(true)
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover rounded-lg transition-colors border border-th-border-secondary"
          >
            <Pencil size={14} />
            Edit
          </button>

          <div className="relative">
            <button
              onClick={() => setShowOverflow(!showOverflow)}
              className="flex items-center p-2 text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover rounded-lg transition-colors border border-th-border-secondary"
            >
              <MoreHorizontal size={16} />
            </button>
            {showOverflow && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowOverflow(false)} />
                <div className="absolute right-0 top-full mt-1 bg-surface-hover border border-th-border-secondary rounded-lg shadow-lg z-20 py-1 min-w-[140px]">
                  <button
                    onClick={() => {
                      setShowOverflow(false)
                      setShowDelete(true)
                    }}
                    className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-th-border-secondary transition-colors"
                  >
                    <Trash2 size={14} />
                    Delete Job
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {(error || deleteError) && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error || deleteError}</p>
        </div>
      )}

      {/* Info Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <p className="text-xs text-th-text-muted uppercase tracking-wider mb-1">Contract Value</p>
          <p className="text-lg font-mono text-brand-purple font-semibold">
            {formatCurrency(job.contract_value)}
          </p>
        </div>

        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <p className="text-xs text-th-text-muted uppercase tracking-wider mb-1">Schedule</p>
          {job.scheduled_date ? (
            <p className="text-sm text-th-text font-mono">
              {new Date(job.scheduled_date + 'T00:00:00').toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          ) : (
            <button
              onClick={() => setShowSchedule(true)}
              className="text-sm text-brand-purple hover:text-brand-purple-text transition-colors"
            >
              Not scheduled
            </button>
          )}
        </div>

        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <p className="text-xs text-th-text-muted uppercase tracking-wider mb-1">Crew</p>
          {job.crew_name ? (
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: job.crew_color || '#6B7280' }}
              />
              <p className="text-sm text-th-text">{job.crew_name}</p>
            </div>
          ) : (
            <p className="text-sm text-th-text-muted">Unassigned</p>
          )}
        </div>

        <div className="bg-surface rounded-xl p-4 border border-th-border">
          <p className="text-xs text-th-text-muted uppercase tracking-wider mb-1">Type</p>
          <p className="text-sm text-th-text capitalize">{job.job_type || '-'}</p>
        </div>
      </div>

      {/* Tab Strip */}
      <div>
        <div className="flex flex-wrap border-b border-th-border mb-0">
          {tabs.map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-3 sm:px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
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
                    ? 'bg-badge-warning-bg text-brand-purple'
                    : 'bg-surface-hover text-th-text-muted'
                }`}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="bg-surface rounded-b-xl rounded-tr-xl p-6">
          {activeTab === 'details' && (
            <DetailsTab
              job={job}
              form={form}
              setForm={setForm}
              editing={editing}
              setEditing={setEditing}
              stages={stages}
              contact={contact}
              saving={saving}
              onSave={handleSave}
              onCancel={cancelEdit}
              formatCurrency={formatCurrency}
            />
          )}
          {activeTab === 'notes' && (
            <NotesTab entityType="job" entityId={Number(id)} />
          )}
          {activeTab === 'estimates' && (
            <JobEstimatesTab
              jobId={Number(id)}
              estimates={estimates}
              onRefresh={() => fetchTabData(id)}
            />
          )}
          {activeTab === 'tasks' && (
            <JobTasksTab
              jobId={Number(id)}
              tasks={tasks}
              onRefresh={() => fetchTabData(id)}
            />
          )}
          {activeTab === 'documents' && (
            <FilesTab
              entityType="job"
              entityId={Number(id)}
              onCountChange={setDocumentCount}
            />
          )}
          {activeTab === 'activity' && (
            <div className="flex flex-col items-center py-12 text-center">
              <Clock size={32} className="text-th-text-muted mb-3" />
              <p className="text-th-text-secondary font-medium">Activity Tracking</p>
              <p className="text-th-text-muted text-sm mt-1">Coming soon</p>
            </div>
          )}
        </div>
      </div>

      {/* Schedule Modal */}
      <QuickScheduleModal
        isOpen={showSchedule}
        onClose={() => setShowSchedule(false)}
        jobId={Number(id)}
        onScheduled={() => {
          getJob(id).then((updated) => {
            setJob(updated)
            setForm(updated)
          })
        }}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={showDelete}
        onConfirm={handleDelete}
        onCancel={() => setShowDelete(false)}
        title="Delete Job"
        message="This action cannot be undone. Are you sure you want to delete this job?"
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}

function DetailsTab({ job, form, setForm, editing, setEditing, stages, contact, saving, onSave, onCancel, formatCurrency }) {
  return (
    <div>
      {editing && (
        <div className="flex justify-end gap-2 mb-4">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={saving}
            className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Pipeline Stage
          </label>
          {editing ? (
            <select
              value={form.stage_id || ''}
              onChange={(e) => setForm({ ...form, stage_id: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            >
              <option value="">None</option>
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm text-th-text">
              {job.stage_name || '-'}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Job Type
          </label>
          {editing ? (
            <select
              value={form.job_type || ''}
              onChange={(e) => setForm({ ...form, job_type: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            >
              <option value="">None</option>
              {JOB_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm text-th-text capitalize">
              {job.job_type || '-'}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Work Type
          </label>
          {editing ? (
            <select
              value={form.work_type || ''}
              onChange={(e) => setForm({ ...form, work_type: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            >
              <option value="">None</option>
              {WORK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm">
              {job.work_type === 'insurance' && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400">
                  Insurance
                </span>
              )}
              {job.work_type === 'retail' && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400">
                  Retail
                </span>
              )}
              {!job.work_type && <span className="text-th-text-muted">-</span>}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Contract Value
          </label>
          {editing ? (
            <input
              type="number"
              step="0.01"
              value={form.contract_value || ''}
              onChange={(e) => setForm({ ...form, contract_value: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text font-mono focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            />
          ) : (
            <p className="text-sm font-mono text-brand-purple">
              {formatCurrency(job.contract_value)}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Lead Source
          </label>
          {editing ? (
            <input
              type="text"
              value={form.lead_source || ''}
              onChange={(e) => setForm({ ...form, lead_source: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
              placeholder="e.g. Google, Referral"
            />
          ) : (
            <p className={`text-sm ${job.lead_source ? 'text-th-text' : 'text-th-text-muted'}`}>
              {job.lead_source || '-'}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Assigned To
          </label>
          <p className={`text-sm ${job.assigned_to_name ? 'text-th-text' : 'text-th-text-muted'}`}>
            {job.assigned_to_name || '-'}
          </p>
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Property Address
          </label>
          {editing ? (
            <input
              type="text"
              value={form.property_address || ''}
              onChange={(e) => setForm({ ...form, property_address: e.target.value })}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            />
          ) : (
            <p className="text-sm">
              <AddressLink address={job.property_address} className="text-th-text" />
            </p>
          )}
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1">
            Notes
          </label>
          {editing ? (
            <textarea
              value={form.notes || ''}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={3}
              className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
            />
          ) : (
            <p className={`text-sm whitespace-pre-wrap ${job.notes ? 'text-th-text' : 'text-th-text-muted'}`}>
              {job.notes || '-'}
            </p>
          )}
        </div>
      </div>

      {/* Contact Info */}
      {contact && (
        <div className="mt-6 pt-6 border-t border-th-border">
          <h3 className="text-xs font-medium text-th-text-muted uppercase tracking-wider mb-3">
            Contact
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Link
                to={`/contacts/${contact.id}`}
                className="text-brand-purple hover:text-brand-purple-text font-medium text-sm transition-colors"
              >
                {contact.name}
              </Link>
            </div>
            {contact.phone && (
              <div>
                <p className="text-xs text-th-text-muted uppercase tracking-wider">Phone</p>
                <p className="text-sm font-mono">
                  <PhoneLink phone={contact.phone} className="text-th-text" />
                </p>
              </div>
            )}
            {contact.email && (
              <div>
                <p className="text-xs text-th-text-muted uppercase tracking-wider">Email</p>
                <p className="text-sm">
                  <a
                    href={`mailto:${contact.email}`}
                    className="text-th-text hover:text-brand-purple transition-colors"
                  >
                    {contact.email}
                  </a>
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-th-border">
        <p className="text-xs text-th-text-muted">
          Created{' '}
          <span className="font-mono">
            {new Date(job.created_at).toLocaleDateString()}
          </span>
        </p>
      </div>
    </div>
  )
}
