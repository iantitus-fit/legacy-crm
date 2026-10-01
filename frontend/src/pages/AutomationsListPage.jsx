import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Zap,
  Plus,
  Edit2,
  Trash2,
  PlayCircle,
  PauseCircle,
} from 'lucide-react'
import {
  listSequences,
  toggleSequence,
  deleteSequence,
} from '../api/automations'
import { useToast } from '../context/ToastContext'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmDialog from '../components/ConfirmDialog'

const TRIGGER_LABELS = {
  contact_created: 'New contact created',
  pipeline_stage_change: 'Contact moves stage',
  estimate_sent: 'Estimate sent',
  estimate_viewed: 'Estimate viewed',
  job_completed: 'Job completed',
  manual: 'Manual enrollment only',
}

const triggerLabel = (t) => TRIGGER_LABELS[t] || t

export default function AutomationsListPage() {
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const navigate = useNavigate()
  const { addToast } = useToast()

  const fetchSequences = () => {
    setLoading(true)
    listSequences()
      .then((data) => setSequences(data.items))
      .catch(() => addToast('Failed to load automations', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchSequences()
  }, [])

  const handleToggle = async (seq, e) => {
    e.stopPropagation()
    try {
      const updated = await toggleSequence(seq.id)
      setSequences((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s)),
      )
      addToast(updated.is_active ? 'Sequence activated' : 'Sequence paused')
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to toggle sequence',
        'error',
      )
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteSequence(deleteTarget.id)
      setSequences((prev) => prev.filter((s) => s.id !== deleteTarget.id))
      addToast('Sequence deleted')
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to delete sequence',
        'error',
      )
    } finally {
      setDeleteTarget(null)
    }
  }

  const createButton = (
    <button
      onClick={() => navigate('/automations/new')}
      className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
    >
      <Plus size={16} />
      New Sequence
    </button>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-th-text">Automations</h1>
          <p className="text-sm text-th-text-muted mt-1">
            Configure follow-up sequences that fire on pipeline events.
          </p>
        </div>
        {createButton}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : sequences.length === 0 ? (
        <EmptyState
          icon={Zap}
          title="No automations yet"
          description="Create your first follow-up sequence to start automating outreach."
          action={createButton}
        />
      ) : (
        <div className="bg-surface rounded-xl overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-th-border">
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Name
                </th>
                <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Trigger
                </th>
                <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Steps
                </th>
                <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Active
                </th>
                <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Total
                </th>
                <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Status
                </th>
                <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {sequences.map((seq) => (
                <tr
                  key={seq.id}
                  onClick={() => navigate(`/automations/${seq.id}`)}
                  className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-sm font-medium text-th-text">
                    {seq.name}
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-secondary">
                    {triggerLabel(seq.trigger_type)}
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-secondary text-center font-mono">
                    {seq.step_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-secondary text-center font-mono">
                    {seq.active_enrollment_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-th-text-muted text-center font-mono">
                    {seq.total_enrollment_count}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={(e) => handleToggle(seq, e)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        seq.is_active
                          ? 'bg-badge-success-bg text-badge-success-text hover:opacity-80'
                          : 'bg-surface-hover text-th-text-muted hover:bg-th-border'
                      }`}
                      title={seq.is_active ? 'Click to pause' : 'Click to activate'}
                    >
                      {seq.is_active ? (
                        <>
                          <PlayCircle size={12} />
                          Active
                        </>
                      ) : (
                        <>
                          <PauseCircle size={12} />
                          Paused
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/automations/${seq.id}`)
                        }}
                        className="text-th-text-muted hover:text-brand-purple p-1 rounded transition-colors"
                        title="Edit"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setDeleteTarget(seq)
                        }}
                        className="text-th-text-muted hover:text-red-500 p-1 rounded transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Delete this sequence?"
        message={
          deleteTarget
            ? `"${deleteTarget.name}" will be deactivated. Active enrollments must be stopped first.`
            : ''
        }
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
