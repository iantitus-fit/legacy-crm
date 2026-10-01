import { useEffect, useRef, useState } from 'react'
import { X, MessageSquare, Mail } from 'lucide-react'
import { createStep, updateStep } from '../api/automations'
import { useToast } from '../context/ToastContext'

const TOKENS = [
  'first_name',
  'last_name',
  'rep_name',
  'company_name',
  'service_type',
  'estimate_total',
  'estimate_link',
  'review_link',
  'company_phone',
]

const PRESETS = [
  { label: 'Immediately', mins: 0 },
  { label: '1 hour', mins: 60 },
  { label: '1 day', mins: 1440 },
  { label: '2 days', mins: 2880 },
  { label: '5 days', mins: 7200 },
  { label: '10 days', mins: 14400 },
  { label: '30 days', mins: 43200 },
  { label: '60 days', mins: 86400 },
  { label: '90 days', mins: 129600 },
  { label: '1 year', mins: 525600 },
]

const minutesToUnit = (mins) => {
  if (mins === 0) return { value: 0, unit: 'minutes' }
  if (mins % 1440 === 0) return { value: mins / 1440, unit: 'days' }
  if (mins % 60 === 0) return { value: mins / 60, unit: 'hours' }
  return { value: mins, unit: 'minutes' }
}

const unitToMinutes = (value, unit) => {
  const v = Number(value) || 0
  if (unit === 'hours') return v * 60
  if (unit === 'days') return v * 1440
  return v
}

export default function StepEditorModal({
  step,
  sequenceId,
  onClose,
  onSaved,
}) {
  const initial = step
    ? {
        channel: step.channel,
        delay_minutes: step.delay_minutes,
        template_body: step.template_body,
        template_subject: step.template_subject || '',
        stop_on_reply: step.stop_on_reply,
        stop_on_stage_change: step.stop_on_stage_change,
      }
    : {
        channel: 'sms',
        delay_minutes: 0,
        template_body: '',
        template_subject: '',
        stop_on_reply: true,
        stop_on_stage_change: true,
      }

  const initDelay = minutesToUnit(initial.delay_minutes)

  const [channel, setChannel] = useState(initial.channel)
  const [delayValue, setDelayValue] = useState(initDelay.value)
  const [delayUnit, setDelayUnit] = useState(initDelay.unit)
  const [body, setBody] = useState(initial.template_body)
  const [subject, setSubject] = useState(initial.template_subject)
  const [stopOnReply, setStopOnReply] = useState(initial.stop_on_reply)
  const [stopOnStageChange, setStopOnStageChange] = useState(
    initial.stop_on_stage_change,
  )
  const [saving, setSaving] = useState(false)

  const textareaRef = useRef(null)
  const { addToast } = useToast()

  // Close on Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const insertToken = (token) => {
    const el = textareaRef.current
    if (!el) {
      setBody((prev) => `${prev}{${token}}`)
      return
    }
    const start = el.selectionStart
    const end = el.selectionEnd
    const insert = `{${token}}`
    setBody((prev) => prev.slice(0, start) + insert + prev.slice(end))
    requestAnimationFrame(() => {
      el.focus()
      const pos = start + insert.length
      el.setSelectionRange(pos, pos)
    })
  }

  const handlePreset = (mins) => {
    const { value, unit } = minutesToUnit(mins)
    setDelayValue(value)
    setDelayUnit(unit)
  }

  const handleSave = async () => {
    if (!body.trim()) {
      addToast('Template body is required', 'error')
      return
    }
    if (channel === 'email' && !subject.trim()) {
      addToast('Subject is required for email steps', 'error')
      return
    }
    setSaving(true)
    const payload = {
      channel,
      delay_minutes: unitToMinutes(delayValue, delayUnit),
      template_body: body,
      template_subject: channel === 'email' ? subject : null,
      stop_on_reply: stopOnReply,
      stop_on_stage_change: stopOnStageChange,
      is_active: true,
    }
    try {
      const saved = step
        ? await updateStep(step.id, payload)
        : await createStep(sequenceId, payload)
      onSaved(saved)
      addToast(step ? 'Step updated' : 'Step added')
    } catch (err) {
      addToast(
        err?.response?.data?.detail || 'Failed to save step',
        'error',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onClick={onClose}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        aria-hidden="true"
      />
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative bg-surface border border-th-border rounded-xl w-full max-w-2xl shadow-2xl max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between p-4 border-b border-th-border">
          <h2 className="text-lg font-semibold text-th-text">
            {step ? 'Edit Step' : 'Add Step'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-th-text-muted hover:text-th-text"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Channel toggle */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
              Channel
            </label>
            <div className="inline-flex bg-page rounded-lg p-1 border border-th-border">
              <button
                type="button"
                onClick={() => setChannel('sms')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  channel === 'sms'
                    ? 'bg-brand-purple text-white'
                    : 'text-th-text-secondary hover:text-th-text'
                }`}
              >
                <MessageSquare size={14} />
                SMS
              </button>
              <button
                type="button"
                onClick={() => setChannel('email')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  channel === 'email'
                    ? 'bg-brand-purple text-white'
                    : 'text-th-text-secondary hover:text-th-text'
                }`}
              >
                <Mail size={14} />
                Email
              </button>
            </div>
          </div>

          {/* Delay */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
              Delay
            </label>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="number"
                min="0"
                value={delayValue}
                onChange={(e) => setDelayValue(e.target.value)}
                className="w-24 bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              />
              <select
                value={delayUnit}
                onChange={(e) => setDelayUnit(e.target.value)}
                className="bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="minutes">minutes</option>
                <option value="hours">hours</option>
                <option value="days">days</option>
              </select>
              <span className="text-xs text-th-text-muted">
                after the previous step (or trigger, for step 1)
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => handlePreset(p.mins)}
                  className="px-2.5 py-1 text-xs rounded bg-surface-hover hover:bg-brand-purple hover:text-white text-th-text-secondary transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Email subject */}
          {channel === 'email' && (
            <div>
              <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
                Subject
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Hi {first_name}, still thinking about your roof?"
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>
          )}

          {/* Template body */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
              Template
            </label>
            <textarea
              ref={textareaRef}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              placeholder={
                channel === 'sms'
                  ? 'Hi {first_name}, this is {rep_name} with Legacy Roofing...'
                  : '<p>Hi {first_name},</p><p>Following up on your estimate...</p>'
              }
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none font-mono"
            />
            <div className="mt-2">
              <div className="text-xs text-th-text-muted mb-1.5">
                Click a token to insert at the cursor:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {TOKENS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => insertToken(t)}
                    className="px-2.5 py-1 text-xs font-mono rounded bg-surface-hover hover:bg-brand-purple hover:text-white text-th-text-secondary transition-colors"
                  >
                    {`{${t}}`}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Stop conditions */}
          <div>
            <label className="block text-xs font-medium text-th-text-muted uppercase tracking-wider mb-2">
              Stop Conditions
            </label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-th-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={stopOnReply}
                  onChange={(e) => setStopOnReply(e.target.checked)}
                  className="rounded border-th-border"
                />
                Stop sequence if the contact replies
              </label>
              <label className="flex items-center gap-2 text-sm text-th-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={stopOnStageChange}
                  onChange={(e) => setStopOnStageChange(e.target.checked)}
                  className="rounded border-th-border"
                />
                Stop sequence if the contact moves stages
              </label>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-th-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving…' : 'Save Step'}
          </button>
        </div>
      </div>
    </div>
  )
}
