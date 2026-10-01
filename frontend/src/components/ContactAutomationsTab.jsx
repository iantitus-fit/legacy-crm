import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, StopCircle, Zap, AlertTriangle } from 'lucide-react'
import {
  getContactEnrollments,
  listSequences,
  manualEnroll,
  stopEnrollment,
  toggleContactAutomations,
} from '../api/automations'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from './LoadingSpinner'
import ConfirmDialog from './ConfirmDialog'

const STATUS_LABELS = {
  active: 'Active',
  completed: 'Completed',
  stopped_reply: 'Stopped — replied',
  stopped_stage_change: 'Stopped — stage change',
  stopped_manual: 'Stopped — manually',
  stopped_optout: 'Stopped — opted out',
}

const formatDate = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export default function ContactAutomationsTab({
  contactId,
  contact,
  onChanged,
}) {
  const [enrollments, setEnrollments] = useState([])
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [enabled, setEnabled] = useState(
    contact?.automations_enabled !== false,
  )
  const [stopTarget, setStopTarget] = useState(null)
  const [enrollPickerOpen, setEnrollPickerOpen] = useState(false)
  const [pickedSequenceId, setPickedSequenceId] = useState('')
  const [enrolling, setEnrolling] = useState(false)
  const { addToast } = useToast()

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      getContactEnrollments(contactId),
      listSequences(),
    ])
      .then(([enrolls, seqs]) => {
        setEnrollments(enrolls.items || [])
        setSequences((seqs.items || []).filter((s) => s.is_active))
      })
      .catch(() => addToast('Failed to load automations', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contactId])

  useEffect(() => {
    setEnabled(contact?.automations_enabled !== false)
  }, [contact])

  const handleToggle = async () => {
    const next = !enabled
    setEnabled(next)
    try {
      await toggleContactAutomations(contactId, next)
      addToast(
        next
          ? 'Automations enabled for this contact'
          : 'Automations disabled for this contact',
      )
      if (onChanged) onChanged()
    } catch (err) {
      setEnabled(!next)
      addToast(
        err?.response?.data?.detail || 'Failed to update setting',
        'error',
      )
    }
  }

  const handleStop = async () => {
    if (!stopTarget) return
    try {
      await stopEnrollment(stopTarget.id, 'stopped from contact page')
      addToast('Enrollment stopped')
      fetchAll()
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to stop enrollment',
        'error',
      )
    } finally {
      setStopTarget(null)
    }
  }

  const handleEnroll = async () => {
    if (!pickedSequenceId) return
    setEnrolling(true)
    try {
      await manualEnroll(contactId, Number(pickedSequenceId))
      addToast('Contact enrolled')
      setEnrollPickerOpen(false)
      setPickedSequenceId('')
      fetchAll()
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to enroll',
        'error',
      )
    } finally {
      setEnrolling(false)
    }
  }

  const active = enrollments.filter((e) => e.status === 'active')
  const past = enrollments.filter((e) => e.status !== 'active')
  const enrollableSequences = sequences.filter(
    (s) => !active.find((e) => e.sequence_id === s.id),
  )

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Per-contact toggle */}
      <div
        className={`rounded-lg p-4 border ${
          enabled
            ? 'bg-surface border-th-border'
            : 'bg-amber-500/10 border-amber-500/30'
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {!enabled && (
              <AlertTriangle
                size={18}
                className="text-amber-400 shrink-0 mt-0.5"
              />
            )}
            <div>
              <div className="font-medium text-th-text">
                {enabled
                  ? 'Automations are enabled for this contact'
                  : 'Automations are paused for this contact'}
              </div>
              <div className="text-sm text-th-text-muted mt-0.5">
                {enabled
                  ? 'Trigger events will enroll this contact in matching sequences.'
                  : 'New enrollments are blocked. Active sequences will not advance.'}
              </div>
            </div>
          </div>
          <button
            onClick={handleToggle}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
              enabled ? 'bg-brand-purple' : 'bg-th-border'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Active enrollments */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Active Enrollments
          </h3>
          {!enrollPickerOpen && enrollableSequences.length > 0 && (
            <button
              onClick={() => setEnrollPickerOpen(true)}
              disabled={!enabled}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text rounded-lg transition-colors disabled:opacity-50"
            >
              <Plus size={12} />
              Enroll in Sequence
            </button>
          )}
        </div>

        {enrollPickerOpen && (
          <div className="bg-page border border-th-border rounded-lg p-3 mb-3 flex items-center gap-2">
            <select
              value={pickedSequenceId}
              onChange={(e) => setPickedSequenceId(e.target.value)}
              className="flex-1 bg-surface border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
            >
              <option value="">Pick a sequence…</option>
              {enrollableSequences.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleEnroll}
              disabled={!pickedSequenceId || enrolling}
              className="px-3 py-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text text-sm font-semibold rounded-lg disabled:opacity-50 transition-colors"
            >
              {enrolling ? 'Enrolling…' : 'Enroll'}
            </button>
            <button
              onClick={() => {
                setEnrollPickerOpen(false)
                setPickedSequenceId('')
              }}
              className="px-3 py-2 text-sm text-th-text-secondary hover:text-th-text"
            >
              Cancel
            </button>
          </div>
        )}

        {active.length === 0 ? (
          <div className="text-sm text-th-text-muted py-3">
            Not currently enrolled in any sequences.
          </div>
        ) : (
          <div className="space-y-2">
            {active.map((e) => (
              <div
                key={e.id}
                className="bg-page border border-th-border rounded-lg p-3 flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Zap size={14} className="text-brand-purple shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-th-text truncate">
                      {e.sequence_name || `Sequence #${e.sequence_id}`}
                    </div>
                    <div className="text-xs text-th-text-muted mt-0.5">
                      Step {e.current_step_order} · Next:{' '}
                      {formatDate(e.next_step_at)}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setStopTarget(e)}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Stop enrollment"
                >
                  <StopCircle size={12} />
                  Stop
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Past enrollments */}
      {past.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-th-text uppercase tracking-wider mb-3">
            History
          </h3>
          <div className="space-y-1.5">
            {past.map((e) => (
              <div
                key={e.id}
                className="flex items-center justify-between py-2 px-3 bg-page/50 rounded text-sm gap-3"
              >
                <div className="min-w-0">
                  <Link
                    to={`/automations/${e.sequence_id}`}
                    className="text-th-text hover:text-brand-purple truncate inline-block"
                  >
                    {e.sequence_name || `Sequence #${e.sequence_id}`}
                  </Link>
                </div>
                <div className="text-xs text-th-text-muted shrink-0">
                  {STATUS_LABELS[e.status] || e.status} ·{' '}
                  {formatDate(e.stopped_at || e.completed_at)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={stopTarget !== null}
        onCancel={() => setStopTarget(null)}
        onConfirm={handleStop}
        title="Stop this enrollment?"
        message={
          stopTarget
            ? `${stopTarget.sequence_name || 'This sequence'} will not advance any further for this contact.`
            : ''
        }
        confirmLabel="Stop Sequence"
        variant="danger"
      />
    </div>
  )
}
