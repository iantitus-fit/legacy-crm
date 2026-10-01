import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  getCOPortalData,
  getCOPortalPreviewUrl,
  getCOPortalPdfUrl,
  submitCOChangeRequest,
  submitCOReject,
  submitCOApprove,
} from '../services/coPortalApi'
import SignaturePad from '../components/SignaturePad'

function StatusBanner({ status }) {
  if (status === 'approved') {
    return (
      <div style={{
        background: '#065f46', color: '#a7f3d0', padding: '12px 24px',
        textAlign: 'center', fontSize: '15px', fontWeight: 600,
      }}>
        This change order has been approved
      </div>
    )
  }
  if (status === 'rejected') {
    return (
      <div style={{
        background: '#7f1d1d', color: '#fecaca', padding: '12px 24px',
        textAlign: 'center', fontSize: '15px', fontWeight: 600,
      }}>
        This change order has been declined
      </div>
    )
  }
  if (status === 'changes_requested') {
    return (
      <div style={{
        background: '#78350f', color: '#fde68a', padding: '12px 24px',
        textAlign: 'center', fontSize: '15px', fontWeight: 600,
      }}>
        Changes have been requested. The team will be in touch.
      </div>
    )
  }
  return null
}

function ChangeRequestModal({ open, onClose, onSubmit }) {
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) { setMessage(''); setError('') }
  }, [open])

  if (!open) return null

  const handleSubmit = async () => {
    if (!message.trim()) { setError('Please describe the changes you\'d like.'); return }
    setLoading(true)
    setError('')
    try {
      await onSubmit(message.trim())
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 16px', fontSize: '18px', fontWeight: 600, color: '#1a1a1a' }}>
          Request Changes
        </h2>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Please describe the changes you'd like..."
          rows={5}
          style={textareaStyle}
        />
        {error && <p style={{ color: '#dc2626', fontSize: '13px', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
          <button onClick={onClose} disabled={loading} style={btnSecondaryStyle}>Cancel</button>
          <button onClick={handleSubmit} disabled={loading} style={btnPrimaryStyle}>
            {loading ? 'Submitting...' : 'Submit Request'}
          </button>
        </div>
      </div>
    </div>
  )
}

function RejectModal({ open, onClose, onSubmit }) {
  const [name, setName] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) { setName(''); setReason(''); setError('') }
  }, [open])

  if (!open) return null

  const handleSubmit = async () => {
    if (!name.trim()) { setError('Please enter your name.'); return }
    setLoading(true)
    setError('')
    try {
      await onSubmit(name.trim(), reason.trim() || undefined)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <h2 style={{ margin: '0 0 16px', fontSize: '18px', fontWeight: 600, color: '#1a1a1a' }}>
          Decline Change Order
        </h2>
        <div style={{ marginBottom: '12px' }}>
          <label style={labelStyle}>Your Name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full name"
            style={inputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>Reason (optional)</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional: let us know why"
            rows={3}
            style={textareaStyle}
          />
        </div>
        {error && <p style={{ color: '#dc2626', fontSize: '13px', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
          <button onClick={onClose} disabled={loading} style={btnSecondaryStyle}>Cancel</button>
          <button onClick={handleSubmit} disabled={loading} style={btnDangerStyle}>
            {loading ? 'Submitting...' : 'Confirm Decline'}
          </button>
        </div>
      </div>
    </div>
  )
}

const TERMS_TEXT = `TERMS AND CONDITIONS

1. Submission Date. The Submission of this Change Order is as stated above. The Customer shall have no more than thirty (30) days from such date to accept this Change Order.

2. Commencement of Work. Following acceptance of this Change Order by the Customer, the additional Work described herein will commence as part of the existing project scope unless otherwise agreed upon.

3. Completion. The estimated completion date of the additional Work is subject to conditions described herein and delays caused by acts of God or events outside the reasonable control of the Company.

4. Payment. Payment for the additional Work shall be made in accordance with the payment schedule outlined. The balance is due upon completion of the additional Work unless otherwise agreed in writing.

5. Warranty. The Company warrants all additional workmanship for a period specified in the original Proposal. Manufacturer warranties on materials apply as provided by the manufacturer.

6. Changes. Any further changes to the scope of work must be agreed upon in writing by both parties and may result in additional charges.`

function ApproveModal({ open, onClose, onSubmit }) {
  const [termsChecked, setTermsChecked] = useState(false)
  const [paymentChecked, setPaymentChecked] = useState(false)
  const [signerName, setSignerName] = useState('')
  const [signatureData, setSignatureData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setTermsChecked(false)
      setPaymentChecked(false)
      setSignerName('')
      setSignatureData(null)
      setError('')
    }
  }, [open])

  if (!open) return null

  const canSubmit = termsChecked && paymentChecked && signerName.trim() && signatureData

  const handleSubmit = async () => {
    if (!canSubmit) return
    setLoading(true)
    setError('')
    try {
      await onSubmit({
        signer_name: signerName.trim(),
        signature_data: signatureData,
        terms_accepted: true,
      })
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div style={overlayStyle}>
      <div style={{ ...modalStyle, maxWidth: '600px' }}>
        <h2 style={{ margin: '0 0 16px', fontSize: '18px', fontWeight: 600, color: '#1a1a1a' }}>
          Approve Change Order
        </h2>

        <div style={{ marginBottom: '16px' }}>
          <label style={labelStyle}>Terms &amp; Conditions</label>
          <div style={{
            maxHeight: '200px', overflowY: 'auto', background: '#f9fafb',
            border: '1px solid #e5e7eb', borderRadius: '8px', padding: '12px 14px',
            fontSize: '13px', lineHeight: 1.6, color: '#374151', whiteSpace: 'pre-wrap',
          }}>
            {TERMS_TEXT}
          </div>
        </div>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '14px', color: '#374151', marginBottom: '8px', cursor: 'pointer' }}>
          <input type="checkbox" checked={termsChecked} onChange={(e) => setTermsChecked(e.target.checked)} style={{ marginTop: '3px' }} />
          I have read and agree to the Terms and Conditions
        </label>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '14px', color: '#374151', marginBottom: '20px', cursor: 'pointer' }}>
          <input type="checkbox" checked={paymentChecked} onChange={(e) => setPaymentChecked(e.target.checked)} style={{ marginTop: '3px' }} />
          I acknowledge the payment schedule
        </label>

        <div style={{ marginBottom: '12px' }}>
          <label style={labelStyle}>Your Full Name *</label>
          <input
            type="text"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            placeholder="Type your full name"
            style={{ ...inputStyle, color: '#1a1a1a', background: '#ffffff' }}
          />
        </div>
        <div style={{ marginBottom: '4px' }}>
          <label style={labelStyle}>Signature *</label>
          <SignaturePad width={560} height={200} onSignatureChange={setSignatureData} />
          <p style={{ fontSize: '12px', color: '#9ca3af', margin: '4px 0 0' }}>
            Sign above using your mouse or finger
          </p>
        </div>

        {error && <p style={{ color: '#dc2626', fontSize: '13px', margin: '8px 0 0' }}>{error}</p>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
          <button onClick={onClose} disabled={loading} style={btnSecondaryStyle}>Cancel</button>
          <button onClick={handleSubmit} disabled={!canSubmit || loading} style={{
            ...btnApproveStyle,
            opacity: (!canSubmit || loading) ? 0.5 : 1,
            cursor: (!canSubmit || loading) ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Submitting...' : 'Submit Approval'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ChangeOrderPortalPage() {
  const { token } = useParams()
  const [coData, setCOData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [showChangeModal, setShowChangeModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [showApproveModal, setShowApproveModal] = useState(false)
  const [confirmation, setConfirmation] = useState(null)

  useEffect(() => {
    getCOPortalData(token)
      .then((data) => setCOData(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f8fafc' }}>
        <div style={{
          width: '40px', height: '40px', border: '3px solid #e2e8f0',
          borderTopColor: '#f59e0b', borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        minHeight: '100vh', background: '#f8fafc', padding: '24px', textAlign: 'center',
      }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>&#128279;</div>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#1e293b', margin: '0 0 8px' }}>
          This link is no longer valid
        </h1>
        <p style={{ fontSize: '15px', color: '#64748b', maxWidth: '400px', lineHeight: 1.6 }}>
          Please contact Legacy Roofing &amp; Exteriors for an updated change order.
        </p>
      </div>
    )
  }

  if (confirmation) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        minHeight: '100vh', background: '#f8fafc', padding: '24px', textAlign: 'center',
      }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>
          {confirmation.type === 'changes' ? '\u2709\uFE0F' : confirmation.type === 'approve' ? '\u2705' : '\u2714\uFE0F'}
        </div>
        <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#1e293b', margin: '0 0 8px' }}>
          {confirmation.title}
        </h1>
        <p style={{ fontSize: '15px', color: '#64748b', maxWidth: '440px', lineHeight: 1.6 }}>
          {confirmation.message}
        </p>
      </div>
    )
  }

  const status = coData?.status
  // Matches the server: only draft / sent / viewed can still be answered.
  const isTerminal = !['draft', 'sent', 'viewed'].includes(status)

  const handleChangeRequest = async (message) => {
    await submitCOChangeRequest(token, message)
    setShowChangeModal(false)
    setConfirmation({
      type: 'changes',
      title: 'Change Request Submitted',
      message: 'Your change request has been submitted. The team will review and get back to you shortly.',
    })
  }

  const handleReject = async (name, reason) => {
    await submitCOReject(token, name, reason)
    setShowRejectModal(false)
    setConfirmation({
      type: 'reject',
      title: 'Change Order Declined',
      message: 'This change order has been declined. If you change your mind, please contact us.',
    })
  }

  const handleApprove = async (data) => {
    await submitCOApprove(token, data)
    setShowApproveModal(false)
    setConfirmation({
      type: 'approve',
      title: 'Change Order Approved!',
      message: 'Thank you! Your approval has been recorded. Legacy Roofing & Exteriors will be in touch shortly.',
    })
  }

  const handleDownloadPdf = () => {
    const link = document.createElement('a')
    link.href = getCOPortalPdfUrl(token)
    link.download = ''
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#f8fafc' }}>
      {/* Top Bar */}
      <div style={topBarStyle}>
        <div style={topBarInnerStyle}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '16px', color: '#1e293b' }}>
              Legacy Roofing &amp; Exteriors
            </div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
              Change Order #{coData?.co_number}{coData?.name ? ` — ${coData.name}` : ''}
            </div>
          </div>
          {!isTerminal && (
            <div style={buttonRowStyle}>
              <button onClick={() => setShowApproveModal(true)} style={btnApproveStyle}>
                Approve &amp; Sign
              </button>
              <button onClick={() => setShowChangeModal(true)} style={btnOutlineStyle}>
                Request Changes
              </button>
              <button onClick={() => setShowRejectModal(true)} style={btnOutlineSubtleStyle}>
                Decline
              </button>
              <button onClick={handleDownloadPdf} style={btnOutlineStyle}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px' }}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                PDF
              </button>
            </div>
          )}
          {isTerminal && (
            <button onClick={handleDownloadPdf} style={btnOutlineStyle}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px' }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download PDF
            </button>
          )}
        </div>
      </div>

      <StatusBanner status={status} />

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <iframe
          src={getCOPortalPreviewUrl(token)}
          title="Change Order Preview"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            display: 'block',
            minHeight: 'calc(100vh - 80px)',
          }}
        />
      </div>

      <ChangeRequestModal
        open={showChangeModal}
        onClose={() => setShowChangeModal(false)}
        onSubmit={handleChangeRequest}
      />
      <RejectModal
        open={showRejectModal}
        onClose={() => setShowRejectModal(false)}
        onSubmit={handleReject}
      />
      <ApproveModal
        open={showApproveModal}
        onClose={() => setShowApproveModal(false)}
        onSubmit={handleApprove}
      />

      <style>{`@media (max-width: 640px) { .portal-btn-row { flex-direction: column; } }`}</style>
    </div>
  )
}

/* --- Styles --- */

const topBarStyle = {
  position: 'sticky', top: 0, zIndex: 40,
  background: '#ffffff',
  borderBottom: '1px solid #e2e8f0',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
}

const topBarInnerStyle = {
  maxWidth: '1200px', margin: '0 auto',
  padding: '12px 24px',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  gap: '12px', flexWrap: 'wrap',
}

const buttonRowStyle = {
  display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap',
}

const overlayStyle = {
  position: 'fixed', inset: 0, zIndex: 50,
  background: 'rgba(0,0,0,0.5)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: '16px',
}

const modalStyle = {
  background: '#ffffff', borderRadius: '12px',
  padding: '24px', width: '100%', maxWidth: '480px',
  boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
}

const labelStyle = {
  display: 'block', fontSize: '13px', fontWeight: 500,
  color: '#374151', marginBottom: '4px',
}

const inputStyle = {
  width: '100%', padding: '10px 12px', fontSize: '14px',
  border: '1px solid #d1d5db', borderRadius: '8px',
  outline: 'none', boxSizing: 'border-box',
}

const textareaStyle = {
  width: '100%', padding: '10px 12px', fontSize: '14px',
  border: '1px solid #d1d5db', borderRadius: '8px',
  outline: 'none', resize: 'vertical', fontFamily: 'inherit',
  boxSizing: 'border-box',
}

const btnBase = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  padding: '8px 18px', fontSize: '14px', fontWeight: 600,
  borderRadius: '8px', cursor: 'pointer', border: 'none',
  transition: 'all 0.15s',
}

const btnApproveStyle = {
  ...btnBase,
  background: '#16a34a', color: '#ffffff',
}

const btnOutlineStyle = {
  ...btnBase,
  background: '#ffffff', color: '#374151',
  border: '1px solid #d1d5db',
}

const btnOutlineSubtleStyle = {
  ...btnBase,
  background: '#ffffff', color: '#6b7280',
  border: '1px solid #e5e7eb',
}

const btnPrimaryStyle = {
  ...btnBase,
  background: '#f59e0b', color: '#1e293b',
}

const btnSecondaryStyle = {
  ...btnBase,
  background: '#f1f5f9', color: '#475569',
}

const btnDangerStyle = {
  ...btnBase,
  background: '#dc2626', color: '#ffffff',
}
