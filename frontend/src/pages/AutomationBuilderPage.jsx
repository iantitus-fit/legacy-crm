import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  ChevronDown,
  MessageSquare,
  Mail,
  Plus,
  Edit2,
  Trash2,
  Clock,
  PlayCircle,
  PauseCircle,
} from 'lucide-react'
import {
  getSequence,
  createSequence,
  updateSequence,
  toggleSequence,
  deleteStep,
} from '../api/automations'
import { listPipelines } from '../api/pipeline'
import { listPipelineStages } from '../api/pipelineStages'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmDialog from '../components/ConfirmDialog'
import StepEditorModal from '../components/StepEditorModal'

const TRIGGER_OPTIONS = [
  { value: 'contact_created', label: 'New contact created' },
  { value: 'pipeline_stage_change', label: 'Contact moves to stage…' },
  { value: 'estimate_sent', label: 'Estimate sent' },
  { value: 'job_completed', label: 'Job completed' },
  { value: 'manual', label: 'Manual enrollment only' },
]

const delayLabel = (mins) => {
  if (!mins) return 'Immediately'
  if (mins < 60) return `${mins} min`
  if (mins < 1440) {
    const hours = mins / 60
    return `${hours} hour${hours === 1 ? '' : 's'}`
  }
  if (mins === 525600) return '1 year'
  const days = Math.round(mins / 1440)
  return `${days} day${days === 1 ? '' : 's'}`
}

export default function AutomationBuilderPage() {
  const { id } = useParams()
  const isNew = id === 'new'
  const navigate = useNavigate()
  const { addToast } = useToast()

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [sequence, setSequence] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [triggerType, setTriggerType] = useState('contact_created')
  const [triggerConfig, setTriggerConfig] = useState({})

  // For pipeline_stage_change trigger
  const [pipelines, setPipelines] = useState([])
  const [stages, setStages] = useState([])
  const [selectedPipelineId, setSelectedPipelineId] = useState('')
  const [selectedStageId, setSelectedStageId] = useState('')

  const [stepModalOpen, setStepModalOpen] = useState(false)
  const [editingStep, setEditingStep] = useState(null)
  const [deleteStepTarget, setDeleteStepTarget] = useState(null)

  useEffect(() => {
    listPipelines()
      .then((data) => setPipelines(data.items || data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (isNew) {
      setLoading(false)
      return
    }
    setLoading(true)
    getSequence(id)
      .then((seq) => {
        setSequence(seq)
        setName(seq.name)
        setDescription(seq.description || '')
        setTriggerType(seq.trigger_type)
        setTriggerConfig(seq.trigger_config || {})
        if (
          seq.trigger_type === 'pipeline_stage_change' &&
          seq.trigger_config
        ) {
          if (seq.trigger_config.to_stage_id) {
            setSelectedStageId(String(seq.trigger_config.to_stage_id))
          }
        }
      })
      .catch(() => {
        addToast('Failed to load sequence', 'error')
        navigate('/automations')
      })
      .finally(() => setLoading(false))
  }, [id, isNew, navigate, addToast])

  // Once we have both pipelines + the loaded sequence's slug, set the
  // selected pipeline id.
  useEffect(() => {
    if (
      triggerType === 'pipeline_stage_change' &&
      triggerConfig.pipeline_slug &&
      pipelines.length > 0 &&
      !selectedPipelineId
    ) {
      const match = pipelines.find((p) => p.slug === triggerConfig.pipeline_slug)
      if (match) setSelectedPipelineId(String(match.id))
    }
  }, [pipelines, triggerType, triggerConfig, selectedPipelineId])

  // When the pipeline selection changes, fetch its stages.
  useEffect(() => {
    if (!selectedPipelineId) {
      setStages([])
      return
    }
    listPipelineStages({ pipelineId: Number(selectedPipelineId) })
      .then((data) => setStages(data.items || data))
      .catch(() => setStages([]))
  }, [selectedPipelineId])

  const handleSave = async () => {
    if (!name.trim()) {
      addToast('Name is required', 'error')
      return
    }
    let config = {}
    if (triggerType === 'pipeline_stage_change') {
      const pipeline = pipelines.find(
        (p) => String(p.id) === String(selectedPipelineId),
      )
      if (!pipeline) {
        addToast('Pick a pipeline for this trigger', 'error')
        return
      }
      config = {
        pipeline_slug: pipeline.slug,
      }
      if (selectedStageId) config.to_stage_id = Number(selectedStageId)
    }
    setSaving(true)
    try {
      if (isNew) {
        const created = await createSequence({
          name: name.trim(),
          description: description || null,
          trigger_type: triggerType,
          trigger_config: config,
          is_active: true,
          steps: [],
        })
        addToast('Sequence created')
        navigate(`/automations/${created.id}`)
      } else {
        const updated = await updateSequence(sequence.id, {
          name: name.trim(),
          description: description || null,
          trigger_type: triggerType,
          trigger_config: config,
        })
        setSequence(updated)
        addToast('Sequence saved')
      }
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to save sequence',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async () => {
    if (isNew || !sequence) return
    try {
      const updated = await toggleSequence(sequence.id)
      setSequence(updated)
      addToast(updated.is_active ? 'Sequence activated' : 'Sequence paused')
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to toggle sequence',
        'error',
      )
    }
  }

  const reloadSequence = async () => {
    if (!sequence) return
    try {
      const seq = await getSequence(sequence.id)
      setSequence(seq)
    } catch {
      /* swallow */
    }
  }

  const handleStepSaved = async () => {
    setStepModalOpen(false)
    setEditingStep(null)
    await reloadSequence()
  }

  const handleDeleteStep = async () => {
    if (!deleteStepTarget) return
    try {
      await deleteStep(deleteStepTarget.id)
      addToast('Step deleted')
      await reloadSequence()
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to delete step',
        'error',
      )
    } finally {
      setDeleteStepTarget(null)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <LoadingSpinner />
      </div>
    )
  }

  const steps = sequence?.steps ? [...sequence.steps].sort((a, b) => a.step_order - b.step_order) : []

  return (
    <div>
      <Link
        to="/automations"
        className="inline-flex items-center gap-1 text-sm text-th-text-muted hover:text-th-text mb-4"
      >
        <ArrowLeft size={14} />
        Back to automations
      </Link>

      <div className="bg-surface rounded-xl p-6 mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Sequence name"
              className="w-full bg-transparent text-2xl font-bold text-th-text border-b border-transparent hover:border-th-border focus:border-brand-purple focus:outline-none transition-colors pb-1"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add a description (optional)"
              rows={2}
              className="w-full mt-2 bg-transparent text-sm text-th-text-secondary border-b border-transparent hover:border-th-border focus:border-brand-purple focus:outline-none resize-none transition-colors pb-1"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {!isNew && sequence && (
              <button
                onClick={handleToggleActive}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  sequence.is_active
                    ? 'bg-badge-success-bg text-badge-success-text'
                    : 'bg-surface-hover text-th-text-muted'
                }`}
              >
                {sequence.is_active ? (
                  <>
                    <PlayCircle size={14} />
                    Active
                  </>
                ) : (
                  <>
                    <PauseCircle size={14} />
                    Paused
                  </>
                )}
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded-lg text-sm disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : isNew ? 'Create Sequence' : 'Save Changes'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-th-border">
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
              Trigger
            </label>
            <div className="relative">
              <select
                value={triggerType}
                onChange={(e) => {
                  setTriggerType(e.target.value)
                  setTriggerConfig({})
                  setSelectedPipelineId('')
                  setSelectedStageId('')
                }}
                className="w-full appearance-none bg-page border border-th-border rounded-lg px-3 py-2 pr-8 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                {TRIGGER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-th-text-muted pointer-events-none"
              />
            </div>
          </div>

          {triggerType === 'pipeline_stage_change' && (
            <>
              <div>
                <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                  Pipeline
                </label>
                <select
                  value={selectedPipelineId}
                  onChange={(e) => {
                    setSelectedPipelineId(e.target.value)
                    setSelectedStageId('')
                  }}
                  className="w-full appearance-none bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                >
                  <option value="">Select a pipeline…</option>
                  {pipelines.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-1.5">
                  Stage (any if blank)
                </label>
                <select
                  value={selectedStageId}
                  onChange={(e) => setSelectedStageId(e.target.value)}
                  disabled={!selectedPipelineId}
                  className="w-full appearance-none bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus disabled:opacity-50"
                >
                  <option value="">Any stage in this pipeline</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Steps timeline */}
      <div className="bg-surface rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-th-text">Steps</h2>
          {!isNew && (
            <button
              onClick={() => {
                setEditingStep(null)
                setStepModalOpen(true)
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text rounded-lg text-sm font-semibold transition-colors"
            >
              <Plus size={14} />
              Add Step
            </button>
          )}
        </div>

        {isNew ? (
          <div className="text-sm text-th-text-muted py-4">
            Save the sequence to start adding steps.
          </div>
        ) : steps.length === 0 ? (
          <div className="text-sm text-th-text-muted py-8 text-center">
            No steps yet. Add the first message in your sequence.
          </div>
        ) : (
          <div className="space-y-0">
            {steps.map((step, idx) => (
              <div key={step.id}>
                <div className="border border-th-border rounded-lg p-4 bg-page">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-semibold text-th-text-muted">
                        Step {step.step_order}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium ${
                          step.channel === 'sms'
                            ? 'bg-blue-500/10 text-blue-400'
                            : 'bg-emerald-500/10 text-emerald-400'
                        }`}
                      >
                        {step.channel === 'sms' ? (
                          <MessageSquare size={11} />
                        ) : (
                          <Mail size={11} />
                        )}
                        {step.channel.toUpperCase()}
                      </span>
                      <span className="text-th-text-muted">
                        · {idx === 0 ? '' : 'Wait '}
                        {delayLabel(step.delay_minutes)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          setEditingStep(step)
                          setStepModalOpen(true)
                        }}
                        className="p-1 text-th-text-muted hover:text-brand-purple rounded transition-colors"
                        title="Edit step"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        onClick={() => setDeleteStepTarget(step)}
                        className="p-1 text-th-text-muted hover:text-red-500 rounded transition-colors"
                        title="Delete step"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  {step.template_subject && (
                    <div className="text-xs text-th-text-secondary mb-1">
                      Subject:{' '}
                      <span className="text-th-text font-medium">
                        {step.template_subject}
                      </span>
                    </div>
                  )}
                  <div className="text-sm text-th-text whitespace-pre-wrap font-mono leading-relaxed">
                    {step.template_body.length > 240
                      ? `${step.template_body.slice(0, 240)}…`
                      : step.template_body}
                  </div>
                  <div className="flex items-center gap-3 mt-3 pt-3 border-t border-th-border text-xs text-th-text-muted">
                    {step.stop_on_reply && (
                      <span className="inline-flex items-center gap-1">
                        ✓ Stop on reply
                      </span>
                    )}
                    {step.stop_on_stage_change && (
                      <span className="inline-flex items-center gap-1">
                        ✓ Stop on stage change
                      </span>
                    )}
                  </div>
                </div>
                {idx < steps.length - 1 && (
                  <div className="flex items-center justify-center py-2 gap-1.5 text-xs text-th-text-muted">
                    <Clock size={12} />
                    Wait {delayLabel(steps[idx + 1].delay_minutes)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {stepModalOpen && sequence && (
        <StepEditorModal
          step={editingStep}
          sequenceId={sequence.id}
          onClose={() => {
            setStepModalOpen(false)
            setEditingStep(null)
          }}
          onSaved={handleStepSaved}
        />
      )}

      <ConfirmDialog
        isOpen={deleteStepTarget !== null}
        onCancel={() => setDeleteStepTarget(null)}
        onConfirm={handleDeleteStep}
        title="Delete this step?"
        message="Active enrollments past this step will continue; future enrollments will skip it."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
