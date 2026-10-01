const BASE = '/api/portal/co'

export async function getCOPortalData(token) {
  const res = await fetch(`${BASE}/${token}`)
  if (!res.ok) {
    const err = new Error('Failed to load change order')
    err.status = res.status
    throw err
  }
  return res.json()
}

export function getCOPortalPreviewUrl(token) {
  return `${BASE}/${token}/preview`
}

export function getCOPortalPdfUrl(token) {
  return `${BASE}/${token}/pdf`
}

export async function submitCOChangeRequest(token, message) {
  const res = await fetch(`${BASE}/${token}/request-changes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to submit change request')
  }
  return res.json()
}

export async function submitCOReject(token, name, reason) {
  const body = { name }
  if (reason) body.reason = reason
  const res = await fetch(`${BASE}/${token}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Failed to submit rejection')
  }
  return res.json()
}

export async function submitCOApprove(token, data) {
  const res = await fetch(`${BASE}/${token}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to submit approval')
  }
  return res.json()
}
