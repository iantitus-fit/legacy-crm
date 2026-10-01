import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRightCircle, Plus, UserPlus, X } from 'lucide-react'
import { convertLead, createLead, listLeads } from '../api/leads'
import { listPipelineStages } from '../api/pipelineStages'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'

const SOURCES = ['Google LSA', 'Website', 'Referral', 'Door Knock', 'Storm', 'Other']
const JOB_TYPES = ['roof', 'gutter', 'siding', 'window']
const WORK_TYPES = ['insurance', 'retail']

const INITIAL_LEAD_FORM = {
  contact_name: '',
  contact_phone: '',
  contact_email: '',
  source: '',
  description: '',
}

const INITIAL_CONVERT_FORM = {
  job_type: '',
  work_type: 'retail',
  property_address: '',
  stage_id: '',
}

export default function LeadsPage() {
  const [leads, setLeads] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [leadForm, setLeadForm] = useState(INITIAL_LEAD_FORM)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showConvertModal, setShowConvertModal] = useState(false)
  const [convertingLead, setConvertingLead] = useState(null)
  const [convertForm, setConvertForm] = useState(INITIAL_CONVERT_FORM)
  const [convertError, setConvertError] = useState('')
  const [converting, setConverting] = useState(false)
  const [stages, setStages] = useState([])
  const navigate = useNavigate()
  const { addToast } = useToast()
  const perPage = 25

  const fetchLeads = () => {
    setLoading(true)
    listLeads({ search, page, perPage })
      .then((data) => {
        setLeads(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load leads', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchLeads()
  }, [search, page])

  const handleSearch = (value) => {
    setSearch(value)
    setPage(1)
  }

  const openAddModal = () => {
    setLeadForm(INITIAL_LEAD_FORM)
    setFormError('')
    setShowAddModal(true)
  }

  const handleCreateLead = async (e) => {
    e.preventDefault()
    setFormError('')
    if (!leadForm.contact_name.trim()) {
      setFormError('Name is required')
      return
    }
    setSaving(true)
    try {
      await createLead({
        contact_name: leadForm.contact_name,
        contact_phone: leadForm.contact_phone || undefined,
        contact_email: leadForm.contact_email || undefined,
        source: leadForm.source || undefined,
        description: leadForm.description || undefined,
      })
      setShowAddModal(false)
      setLeadForm(INITIAL_LEAD_FORM)
      addToast('Lead created successfully')
      fetchLeads()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create lead')
    } finally {
      setSaving(false)
    }
  }

  const openConvertModal = async (lead) => {
    setConvertingLead(lead)
    setConvertForm(INITIAL_CONVERT_FORM)
    setConvertError('')
    setShowConvertModal(true)
    try {
      const stageData = await listPipelineStages()
      setStages(stageData.items)
      if (stageData.items.length > 0) {
        setConvertForm((f) => ({ ...f, stage_id: stageData.items[0].id }))
      }
    } catch {
      // silently fail
    }
  }

  const handleConvert = async (e) => {
    e.preventDefault()
    setConvertError('')
    setConverting(true)
    try {
      const result = await convertLead(convertingLead.id, {
        job_type: convertForm.job_type || undefined,
        work_type: convertForm.work_type || undefined,
        property_address: convertForm.property_address || undefined,
        stage_id: convertForm.stage_id ? Number(convertForm.stage_id) : undefined,
      })
      setShowConvertModal(false)
      addToast('Lead converted to client')
      // Sprint 15e — land on the client profile in the new model
      navigate(`/contacts/${result.contact_id}`)
    } catch (err) {
      setConvertError(err.response?.data?.detail || 'Failed to convert lead')
    } finally {
      setConverting(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-th-text">Leads</h1>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
        >
          <Plus size={16} />
          Add Lead
        </button>
      </div>

      {/* Search */}
      <div className="mb-4 max-w-sm">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Search by name or source..."
        />
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner centered />
      ) : leads.length === 0 ? (
        <EmptyState
          icon={UserPlus}
          title={search ? 'No leads found' : 'No leads yet'}
          description={
            search
              ? 'Try a different search term'
              : 'Add your first lead to start tracking prospects'
          }
          action={
            !search && (
              <button
                onClick={openAddModal}
                className="text-brand-purple hover:text-brand-purple-text text-sm font-medium"
              >
                Add your first lead
              </button>
            )
          }
        />
      ) : (
        <>
          <div className="bg-surface rounded-xl overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-th-border">
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Phone
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Email
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Source
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Created
                  </th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-th-text">
                      {lead.contact_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary font-mono">
                      {lead.contact_phone || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {lead.contact_email || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {lead.source || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-muted font-mono">
                      {new Date(lead.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => openConvertModal(lead)}
                        className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-purple hover:text-brand-purple-text transition-colors"
                      >
                        <ArrowRightCircle size={14} />
                        Convert to Job
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

      {/* Add Lead Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowAddModal(false)}
          />
          <div className="relative bg-surface rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-th-text">Add Lead</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-th-text-muted hover:text-th-text"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateLead} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={leadForm.contact_name}
                  onChange={(e) =>
                    setLeadForm({ ...leadForm, contact_name: e.target.value })
                  }
                  required
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="John Smith"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Phone
                  </label>
                  <input
                    type="tel"
                    value={leadForm.contact_phone}
                    onChange={(e) =>
                      setLeadForm({ ...leadForm, contact_phone: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="765-555-1234"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    value={leadForm.contact_email}
                    onChange={(e) =>
                      setLeadForm({ ...leadForm, contact_email: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                    placeholder="john@example.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Source
                </label>
                <select
                  value={leadForm.source}
                  onChange={(e) =>
                    setLeadForm({ ...leadForm, source: e.target.value })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                >
                  <option value="">Select source...</option>
                  {SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Description
                </label>
                <textarea
                  value={leadForm.description}
                  onChange={(e) =>
                    setLeadForm({ ...leadForm, description: e.target.value })
                  }
                  rows={3}
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="Details about the lead..."
                />
              </div>

              {formError && (
                <p className="text-red-400 text-sm">{formError}</p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Add Lead'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Convert to Job Modal */}
      {showConvertModal && convertingLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowConvertModal(false)}
          />
          <div className="relative bg-surface rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-th-text">
                Convert Lead to Job
              </h2>
              <button
                onClick={() => setShowConvertModal(false)}
                className="text-th-text-muted hover:text-th-text"
              >
                <X size={20} />
              </button>
            </div>

            <div className="bg-surface-hover/50 rounded-lg px-4 py-3 mb-4">
              <p className="text-sm text-th-text font-medium">
                {convertingLead.contact_name}
              </p>
              {convertingLead.contact_phone && (
                <p className="text-xs text-th-text-muted font-mono mt-0.5">
                  {convertingLead.contact_phone}
                </p>
              )}
              {convertingLead.source && (
                <p className="text-xs text-th-text-muted mt-0.5">
                  Source: {convertingLead.source}
                </p>
              )}
            </div>

            <form onSubmit={handleConvert} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Pipeline Stage
                </label>
                <select
                  value={convertForm.stage_id}
                  onChange={(e) =>
                    setConvertForm({ ...convertForm, stage_id: e.target.value })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                >
                  <option value="">Default (first stage)</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Job Type
                  </label>
                  <select
                    value={convertForm.job_type}
                    onChange={(e) =>
                      setConvertForm({ ...convertForm, job_type: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  >
                    <option value="">Select type...</option>
                    {JOB_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-th-text-secondary mb-1">
                    Work Type
                  </label>
                  <select
                    value={convertForm.work_type}
                    onChange={(e) =>
                      setConvertForm({ ...convertForm, work_type: e.target.value })
                    }
                    className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  >
                    {WORK_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-th-text-secondary mb-1">
                  Property Address
                </label>
                <input
                  type="text"
                  value={convertForm.property_address}
                  onChange={(e) =>
                    setConvertForm({
                      ...convertForm,
                      property_address: e.target.value,
                    })
                  }
                  className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
                  placeholder="Leave blank to use contact address"
                />
              </div>

              {convertError && (
                <p className="text-red-400 text-sm">{convertError}</p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConvertModal(false)}
                  className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={converting}
                  className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {converting ? 'Converting...' : 'Convert to Job'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
