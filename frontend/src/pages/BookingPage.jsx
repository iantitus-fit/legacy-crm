import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle2, Loader2 } from 'lucide-react'
import axios from 'axios'

const SERVICE_OPTIONS = [
  'Roofing',
  'Gutters',
  'Siding',
  'Windows',
  'Painting',
  'Other',
]

// Mapping from short ?source= tokens to the lead_source strings that show
// up in reports. Anything not in the map is passed through as-is so Dale
// can drop fresh source codes onto a new landing page without code changes.
const SOURCE_ALIASES = {
  google_lsa: 'Google LSA',
  google_ads: 'Google Ads',
  facebook: 'Facebook',
  door_hanger: 'Door Hanger',
  referral: 'Referral',
  yard_sign: 'Yard Sign',
}

function resolveLeadSource(rawParam) {
  if (!rawParam) return null
  return SOURCE_ALIASES[rawParam] || rawParam
}

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  address: '',
  city: '',
  state: 'IN',
  zip: '',
  service_type: '',
  message: '',
  // Honeypot — real users never fill this; bots auto-fill any visible field.
  company_website: '',
}

export default function BookingPage() {
  const [searchParams] = useSearchParams()
  const leadSource = resolveLeadSource(searchParams.get('source'))

  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.title = 'Request a Free Estimate — Legacy Roofing & Exteriors'
  }, [])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const payload = {
        ...form,
        service_type: form.service_type || null,
        email: form.email || null,
        address: form.address || null,
        city: form.city || null,
        zip: form.zip || null,
        message: form.message || null,
        lead_source: leadSource,
      }
      await axios.post('/api/public/book', payload)
      setSuccess(true)
    } catch (err) {
      const status = err?.response?.status
      if (status === 429) {
        setError(
          err.response.data?.detail ||
            'Too many submissions. Please try again in an hour or call us directly.'
        )
      } else if (status === 422) {
        setError('Please fill in all required fields and try again.')
      } else {
        setError('Something went wrong. Please try again or call us directly.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <PageShell>
        <div className="text-center py-12">
          <CheckCircle2 size={56} className="mx-auto text-emerald-500 mb-4" />
          <h1 className="text-2xl font-semibold text-slate-900 mb-2">
            Thanks! We'll be in touch within 24 hours.
          </h1>
          <p className="text-slate-600 max-w-md mx-auto">
            A member of the Legacy Roofing team will reach out shortly to
            schedule your free inspection.
          </p>
          <p className="text-slate-500 text-sm mt-6">
            Need to reach us sooner?{' '}
            <a href="tel:+16155550100" className="text-violet-700 font-medium">
              (615) 555-0100
            </a>
          </p>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <h1 className="text-2xl font-semibold text-slate-900 mb-2">
        Request a free estimate
      </h1>
      <p className="text-slate-600 mb-6">
        Tell us a little about your project and we'll be in touch within one
        business day.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Row>
          <Field
            label="First name"
            name="first_name"
            value={form.first_name}
            onChange={handleChange}
            required
            autoComplete="given-name"
          />
          <Field
            label="Last name"
            name="last_name"
            value={form.last_name}
            onChange={handleChange}
            required
            autoComplete="family-name"
          />
        </Row>

        <Row>
          <Field
            label="Phone"
            name="phone"
            type="tel"
            value={form.phone}
            onChange={handleChange}
            required
            autoComplete="tel"
            placeholder="(555) 555-0100"
          />
          <Field
            label="Email (optional)"
            name="email"
            type="email"
            value={form.email}
            onChange={handleChange}
            autoComplete="email"
          />
        </Row>

        <Field
          label="Street address (optional)"
          name="address"
          value={form.address}
          onChange={handleChange}
          autoComplete="street-address"
        />

        <Row>
          <Field
            label="City"
            name="city"
            value={form.city}
            onChange={handleChange}
            autoComplete="address-level2"
          />
          <Field
            label="State"
            name="state"
            value={form.state}
            onChange={handleChange}
            autoComplete="address-level1"
          />
          <Field
            label="ZIP"
            name="zip"
            value={form.zip}
            onChange={handleChange}
            autoComplete="postal-code"
          />
        </Row>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Service needed
          </label>
          <select
            name="service_type"
            value={form.service_type}
            onChange={handleChange}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-600 focus:ring-2 focus:ring-violet-200 focus:outline-none text-slate-900 bg-white"
          >
            <option value="">Choose a service…</option>
            {SERVICE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Tell us about your project (optional)
          </label>
          <textarea
            name="message"
            value={form.message}
            onChange={handleChange}
            rows={4}
            placeholder="What's going on with the property? Any specific concerns?"
            className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-600 focus:ring-2 focus:ring-violet-200 focus:outline-none text-slate-900 bg-white resize-y"
          />
        </div>

        {/* Honeypot — hidden visually + via autocomplete. Bots that fill every
            field will trip this and be silently dropped server-side. */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            left: '-9999px',
            width: '1px',
            height: '1px',
            overflow: 'hidden',
          }}
        >
          <label htmlFor="company_website">
            Leave this field blank
            <input
              type="text"
              id="company_website"
              name="company_website"
              tabIndex={-1}
              autoComplete="off"
              value={form.company_website}
              onChange={handleChange}
            />
          </label>
        </div>

        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-800">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-violet-700 hover:bg-violet-800 text-white font-semibold transition-colors disabled:opacity-60"
        >
          {submitting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Sending…
            </>
          ) : (
            'Get my free estimate'
          )}
        </button>

        <p className="text-xs text-slate-500 text-center">
          By submitting this form you agree to be contacted by Legacy Roofing
          &amp; Exteriors about your project. We never share your info.
        </p>
      </form>
    </PageShell>
  )
}

function PageShell({ children }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-violet-50 to-slate-50 py-8 px-4 sm:py-12">
      <div className="max-w-xl mx-auto">
        <header className="flex items-center justify-center mb-6">
          <img
            src="/static/logo.png"
            alt="Legacy Roofing & Exteriors"
            className="h-12 w-auto"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
          />
        </header>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sm:p-8">
          {children}
        </div>
        <footer className="text-center text-xs text-slate-500 mt-6">
          Legacy Roofing &amp; Exteriors &middot; Kokomo, IN
        </footer>
      </div>
    </div>
  )
}

function Row({ children }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{children}</div>
}

function Field({ label, name, type = 'text', value, onChange, required, autoComplete, placeholder }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-slate-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        required={required}
        autoComplete={autoComplete}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-violet-600 focus:ring-2 focus:ring-violet-200 focus:outline-none text-slate-900 bg-white"
      />
    </div>
  )
}
