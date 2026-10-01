import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { Filter, Plus, X } from 'lucide-react'
import {
  listPipelines,
  getPipelineBoard,
  getContactsBoard,
  getEstimatesBoard,
} from '../api/pipeline'
import { updateJobStage } from '../api/jobs'
import { updateContact } from '../api/contacts'
import { updateEstimate } from '../api/estimates'
import { useToast } from '../context/ToastContext'
import PipelineBoardCard, { PipelineBoardCardContent } from '../components/PipelineBoardCard'
import LoadingSpinner from '../components/LoadingSpinner'
import QuickCreateLeadModal from '../components/QuickCreateLeadModal'
import JobPickerModal from '../components/JobPickerModal'
import { createEstimate } from '../api/estimates'

const formatCurrency = (value) => {
  if (!value) return '$0'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function StageColumn({ stage, children }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `stage-${stage.id}`,
    data: { stage },
  })

  return (
    <div
      ref={setNodeRef}
      className={`flex-shrink-0 w-72 flex flex-col rounded-xl bg-surface/50 ${
        isOver ? 'ring-2 ring-brand-purple/40' : ''
      }`}
    >
      {/* Colored top bar */}
      <div
        className="h-1 rounded-t-xl"
        style={{ backgroundColor: stage.color || '#6B7280' }}
      />

      {/* Column header */}
      <div className="p-3 border-b border-th-border/50">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-th-text truncate">
            {stage.name}
          </h3>
          <span className="text-xs text-th-text-muted font-mono ml-2 bg-surface-hover px-1.5 py-0.5 rounded">
            {stage.job_count}
          </span>
        </div>
        <p className="text-xs font-mono text-brand-purple/70 mt-0.5">
          {formatCurrency(stage.total_value)}
        </p>
      </div>

      {/* Jobs list */}
      <div className="flex-1 p-2 space-y-2 overflow-y-auto min-h-[100px] max-h-[calc(100vh-280px)]">
        {children}
      </div>
    </div>
  )
}

export default function PipelineBoardPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()

  const [pipeline, setPipeline] = useState(null)
  const [board, setBoard] = useState([])
  const [totalDeals, setTotalDeals] = useState(0)
  const [totalValue, setTotalValue] = useState(0)
  const [loading, setLoading] = useState(true)
  const [activeJob, setActiveJob] = useState(null)
  const [showLeadModal, setShowLeadModal] = useState(false)
  const [showEstimateJobPicker, setShowEstimateJobPicker] = useState(false)

  // Filters
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState({})
  const [pendingFilters, setPendingFilters] = useState({
    salesperson: '',
    lead_source: '',
    label: '',
    created_after: '',
    created_before: '',
  })

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  )

  // Sprint 15c — slug-driven entity routing
  // leads / sales → contacts  (click → /contacts/:id)
  // jobs          → estimates (click → /estimates/:id)
  // anything else → legacy jobs board (unchanged)
  const entityType =
    slug === 'leads' || slug === 'sales'
      ? 'contact'
      : slug === 'jobs'
      ? 'estimate'
      : 'job'

  const fetchBoard = useCallback(
    async (currentFilters = {}) => {
      setLoading(true)
      try {
        const pipelines = await listPipelines()
        const found = pipelines.items.find((p) => p.slug === slug)
        if (!found) {
          addToast('Pipeline not found', 'error')
          navigate('/dashboard')
          return
        }
        setPipeline(found)

        if (entityType === 'contact') {
          const data = await getContactsBoard(found.id)
          setBoard(
            data.stages.map((stage) => ({
              ...stage,
              job_count: stage.contact_count,
              jobs: stage.contacts.map((c) => ({
                id: c.id,
                contact_id: c.id,
                contact_name: c.name,
                display_name: c.company || c.name,
                property_address: c.address,
                contract_value: c.active_estimate_value,
                lead_source: c.lead_source,
                labels: null,
                work_type: null,
                job_type: c.client_type,
                crew_name: null,
                crew_color: null,
                assigned_to_name: null,
                last_activity_at: c.last_activity_at,
                stage_id: c.stage_id,
                _entity_type: 'contact',
              })),
            }))
          )
          setTotalDeals(data.total_contacts)
          setTotalValue(data.total_value)
        } else if (entityType === 'estimate') {
          const data = await getEstimatesBoard(found.id)
          setBoard(
            data.stages.map((stage) => ({
              ...stage,
              job_count: stage.estimate_count,
              jobs: stage.estimates.map((e) => ({
                id: e.id,
                contact_id: e.contact_id,
                contact_name: e.contact_name,
                display_name: e.name || `Estimate #${e.id}`,
                property_address: e.location_address,
                contract_value: e.total,
                lead_source: null,
                labels: null,
                work_type: e.work_type,
                job_type: e.job_type,
                crew_id: e.crew_id,
                crew_name: e.crew_name,
                crew_color: e.crew_color,
                assigned_to_name: e.assigned_to_name,
                scheduled_date: e.scheduled_start,
                last_activity_at: e.approved_at,
                stage_id: e.stage_id,
                _entity_type: 'estimate',
              })),
            }))
          )
          setTotalDeals(data.total_estimates)
          setTotalValue(data.total_value)
        } else {
          const data = await getPipelineBoard(found.id, currentFilters)
          setBoard(
            data.stages.map((stage) => ({
              ...stage,
              jobs: stage.jobs.map((j) => ({ ...j, _entity_type: 'job' })),
            }))
          )
          setTotalDeals(data.total_deals)
          setTotalValue(data.total_value)
        }
      } catch {
        addToast('Failed to load pipeline board', 'error')
      } finally {
        setLoading(false)
      }
    },
    [slug, addToast, navigate, entityType]
  )

  useEffect(() => {
    setFilters({})
    setPendingFilters({
      salesperson: '',
      lead_source: '',
      label: '',
      created_after: '',
      created_before: '',
    })
    fetchBoard({})
  }, [slug])

  const applyFilters = () => {
    const active = {}
    if (pendingFilters.salesperson) active.salesperson = pendingFilters.salesperson
    if (pendingFilters.lead_source) active.lead_source = pendingFilters.lead_source
    if (pendingFilters.label) active.label = pendingFilters.label
    if (pendingFilters.created_after) active.created_after = pendingFilters.created_after
    if (pendingFilters.created_before) active.created_before = pendingFilters.created_before
    setFilters(active)
    fetchBoard(active)
    setShowFilters(false)
  }

  const resetFilters = () => {
    setPendingFilters({
      salesperson: '',
      lead_source: '',
      label: '',
      created_after: '',
      created_before: '',
    })
    setFilters({})
    fetchBoard({})
    setShowFilters(false)
  }

  const hasActiveFilters = Object.keys(filters).length > 0

  const handleDragStart = (event) => {
    setActiveJob(event.active.data.current?.job || null)
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveJob(null)

    if (!over) return

    const job = active.data.current?.job
    if (!job) return

    let targetStageId = null
    if (over.id.toString().startsWith('stage-')) {
      targetStageId = Number(over.id.toString().replace('stage-', ''))
    } else if (over.data.current?.job) {
      const overJob = over.data.current.job
      targetStageId = overJob.stage_id
    }

    if (!targetStageId) return

    const currentStage = board.find((s) =>
      s.jobs.some((j) => j.id === job.id)
    )
    if (!currentStage || currentStage.id === targetStageId) return

    // Optimistic update
    let previousBoard = null
    setBoard((prev) => {
      previousBoard = prev.map((s) => ({ ...s, jobs: [...s.jobs] }))
      return prev.map((stage) => {
        const without = stage.jobs.filter((j) => j.id !== job.id)

        if (stage.id === targetStageId) {
          const movedJob = { ...job, stage_id: targetStageId }
          const newJobs = [movedJob, ...without]
          return {
            ...stage,
            jobs: newJobs,
            job_count: newJobs.length,
            total_value: newJobs.reduce(
              (sum, j) => sum + (parseFloat(j.contract_value) || 0),
              0
            ),
          }
        }

        if (without.length !== stage.jobs.length) {
          return {
            ...stage,
            jobs: without,
            job_count: without.length,
            total_value: without.reduce(
              (sum, j) => sum + (parseFloat(j.contract_value) || 0),
              0
            ),
          }
        }

        return stage
      })
    })

    try {
      if (job._entity_type === 'contact') {
        await updateContact(job.id, { stage_id: targetStageId })
      } else if (job._entity_type === 'estimate') {
        await updateEstimate(job.id, { stage_id: targetStageId })
      } else {
        await updateJobStage(job.id, targetStageId)
      }
    } catch {
      setBoard(previousBoard)
      addToast('Failed to move card')
    }
  }

  const handleDragCancel = () => {
    setActiveJob(null)
  }

  if (loading) {
    return <LoadingSpinner centered />
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-th-text">
            {pipeline?.name || 'Pipeline'}
          </h1>
          <span className="text-xs font-mono bg-surface-hover text-th-text-secondary px-2 py-1 rounded">
            {totalDeals} deal{totalDeals !== 1 ? 's' : ''}
          </span>
          <span className="text-sm font-mono text-brand-purple">
            {formatCurrency(totalValue)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              hasActiveFilters
                ? 'bg-badge-warning-bg text-brand-purple hover:bg-badge-warning-bg'
                : 'text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover'
            }`}
          >
            <Filter size={16} />
            Filters
            {hasActiveFilters && (
              <span className="w-2 h-2 rounded-full bg-btn-primary-bg" />
            )}
          </button>
          {slug === 'leads' && (
            <button
              onClick={() => setShowLeadModal(true)}
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              <Plus size={16} />
              Add Lead
            </button>
          )}
          {slug === 'sales' && (
            <button
              onClick={() => setShowEstimateJobPicker(true)}
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              <Plus size={16} />
              New Estimate
            </button>
          )}
          {slug !== 'leads' && slug !== 'sales' && (
            <button
              onClick={() => navigate('/jobs')}
              className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
            >
              <Plus size={16} />
              Add Job
            </button>
          )}
        </div>
      </div>

      {showLeadModal && (
        <QuickCreateLeadModal
          onClose={() => setShowLeadModal(false)}
          onCreated={() => fetchBoard(filters)}
        />
      )}
      {showEstimateJobPicker && (
        <JobPickerModal
          title="Select a Job for the New Estimate"
          onClose={() => setShowEstimateJobPicker(false)}
          onPick={async (jobId) => {
            setShowEstimateJobPicker(false)
            try {
              const est = await createEstimate({ job_id: jobId, name: '' })
              addToast('Estimate created')
              navigate(`/estimates/${est.id}`)
            } catch (err) {
              addToast(err?.response?.data?.detail || 'Failed to create estimate', 'error')
            }
          }}
        />
      )}

      {/* Filter bar */}
      {showFilters && (
        <div className="bg-surface rounded-xl p-4 mb-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="block text-xs font-medium text-th-text-muted mb-1">
                Lead Source
              </label>
              <input
                type="text"
                value={pendingFilters.lead_source}
                onChange={(e) =>
                  setPendingFilters({ ...pendingFilters, lead_source: e.target.value })
                }
                placeholder="e.g. Google"
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-th-text-muted mb-1">
                Label
              </label>
              <input
                type="text"
                value={pendingFilters.label}
                onChange={(e) =>
                  setPendingFilters({ ...pendingFilters, label: e.target.value })
                }
                placeholder="e.g. urgent"
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-th-text-muted mb-1">
                Created After
              </label>
              <input
                type="date"
                value={pendingFilters.created_after}
                onChange={(e) =>
                  setPendingFilters({ ...pendingFilters, created_after: e.target.value })
                }
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-th-text-muted mb-1">
                Created Before
              </label>
              <input
                type="date"
                value={pendingFilters.created_before}
                onChange={(e) =>
                  setPendingFilters({ ...pendingFilters, created_before: e.target.value })
                }
                className="w-full bg-surface-hover border border-th-border-secondary rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                onClick={applyFilters}
                className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Apply
              </button>
              <button
                onClick={resetFilters}
                className="text-th-text-secondary hover:text-th-text px-3 py-2 text-sm transition-colors"
              >
                Reset
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="flex gap-4 overflow-x-auto pb-4">
          {board.map((stage) => (
            <SortableContext
              key={stage.id}
              id={`stage-${stage.id}`}
              items={stage.jobs.map((j) => `job-${j.id}`)}
              strategy={verticalListSortingStrategy}
            >
              <StageColumn stage={stage}>
                {stage.jobs.map((job) => (
                  <PipelineBoardCard key={job.id} job={job} />
                ))}
              </StageColumn>
            </SortableContext>
          ))}
        </div>

        <DragOverlay>
          {activeJob ? (
            <PipelineBoardCardContent
              job={activeJob}
              className="bg-surface-hover rounded-lg p-3 cursor-grabbing shadow-xl ring-1 ring-brand-purple/30"
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
