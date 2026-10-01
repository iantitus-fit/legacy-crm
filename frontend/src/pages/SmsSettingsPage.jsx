import { useEffect, useState } from 'react'
import { Loader2, MessageCircle, Save } from 'lucide-react'
import { getSmsConfig, updateSmsConfig } from '../api/sms'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'

const TOKEN_HELP =
  'Available tokens: {first_name}, {last_name}, {full_name}, {company_name}, {rep_name}, {estimate_url}'

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-th-text mb-1">
        {label}
      </label>
      {children}
      {hint && (
        <p className="mt-1 text-xs text-th-text-muted">{hint}</p>
      )}
    </div>
  )
}

function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`mt-0.5 relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
          checked ? 'bg-brand-purple' : 'bg-surface-hover'
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
            checked ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </button>
      <div>
        <div className="text-sm font-medium text-th-text">{label}</div>
        {description && (
          <div className="text-xs text-th-text-muted">{description}</div>
        )}
      </div>
    </label>
  )
}

export default function SmsSettingsPage() {
  const { addToast } = useToast()
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getSmsConfig()
      .then(setConfig)
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError('Admin access required to view SMS settings.')
        } else {
          setError('Failed to load SMS settings.')
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const setField = (field, value) => {
    setConfig((c) => ({ ...c, [field]: value }))
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    try {
      const payload = {
        auto_respond_new_lead: config.auto_respond_new_lead,
        auto_respond_after_hours: config.auto_respond_after_hours,
        business_hours_start: config.business_hours_start,
        business_hours_end: config.business_hours_end,
        business_timezone: config.business_timezone,
        new_lead_template: config.new_lead_template,
        after_hours_template: config.after_hours_template,
        estimate_sent_template: config.estimate_sent_template,
        opt_out_keywords: config.opt_out_keywords,
        opt_in_keywords: config.opt_in_keywords,
        help_response: config.help_response,
      }
      const updated = await updateSmsConfig(payload)
      setConfig(updated)
      addToast('SMS settings saved', 'success')
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to save settings'
      addToast(detail, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingSpinner />

  if (error || !config) {
    return (
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold text-th-text mb-2">
          SMS Settings
        </h1>
        <p className="text-sm text-th-text-muted">{error || 'No config available.'}</p>
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <MessageCircle size={22} className="text-brand-purple" />
        <h1 className="text-2xl font-semibold text-th-text">SMS Settings</h1>
      </div>

      <div className="space-y-8">
        {/* Auto-respond toggles */}
        <section className="bg-surface rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Auto-Response
          </h2>
          <Toggle
            checked={config.auto_respond_new_lead}
            onChange={(v) => setField('auto_respond_new_lead', v)}
            label="Auto-respond to new leads"
            description="Send a text immediately when a new contact lands in the Leads pipeline."
          />
          <Toggle
            checked={config.auto_respond_after_hours}
            onChange={(v) => setField('auto_respond_after_hours', v)}
            label="Auto-respond after hours"
            description="Use the after-hours template when a new lead arrives outside business hours."
          />
        </section>

        {/* Business hours */}
        <section className="bg-surface rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Business Hours
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Start">
              <input
                type="time"
                value={config.business_hours_start?.slice(0, 5) || '08:00'}
                onChange={(e) =>
                  setField('business_hours_start', `${e.target.value}:00`)
                }
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </Field>
            <Field label="End">
              <input
                type="time"
                value={config.business_hours_end?.slice(0, 5) || '18:00'}
                onChange={(e) =>
                  setField('business_hours_end', `${e.target.value}:00`)
                }
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </Field>
          </div>
          <Field label="Timezone" hint="IANA timezone (e.g., America/Indiana/Indianapolis)">
            <input
              type="text"
              value={config.business_timezone || ''}
              onChange={(e) => setField('business_timezone', e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </Field>
        </section>

        {/* Templates */}
        <section className="bg-surface rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Templates
          </h2>
          <p className="text-xs text-th-text-muted">{TOKEN_HELP}</p>
          <Field label="New lead (business hours)">
            <textarea
              value={config.new_lead_template}
              onChange={(e) => setField('new_lead_template', e.target.value)}
              rows={3}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
            />
          </Field>
          <Field label="New lead (after hours)">
            <textarea
              value={config.after_hours_template}
              onChange={(e) => setField('after_hours_template', e.target.value)}
              rows={3}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
            />
          </Field>
          <Field label="Estimate sent">
            <textarea
              value={config.estimate_sent_template}
              onChange={(e) => setField('estimate_sent_template', e.target.value)}
              rows={3}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
            />
          </Field>
          <Field label="Help response" hint="Sent automatically when a customer texts HELP.">
            <textarea
              value={config.help_response}
              onChange={(e) => setField('help_response', e.target.value)}
              rows={2}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-none"
            />
          </Field>
        </section>

        {/* Keywords */}
        <section className="bg-surface rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-th-text uppercase tracking-wider">
            Opt-Out / Opt-In Keywords
          </h2>
          <Field
            label="Opt-out keywords"
            hint="Comma-separated. When a contact texts any of these, they're opted out."
          >
            <input
              type="text"
              value={config.opt_out_keywords}
              onChange={(e) => setField('opt_out_keywords', e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm font-mono text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </Field>
          <Field label="Opt-in keywords" hint="Comma-separated. Texts these resume sending.">
            <input
              type="text"
              value={config.opt_in_keywords}
              onChange={(e) => setField('opt_in_keywords', e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm font-mono text-th-text focus:outline-none focus:border-th-border-focus"
            />
          </Field>
        </section>

        <div className="flex justify-end pb-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-brand-purple hover:bg-brand-purple/90 disabled:opacity-50 rounded-lg transition-colors"
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save size={16} />
                Save settings
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
