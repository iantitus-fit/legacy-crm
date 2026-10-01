const BASE = '/api/portal'

export async function getPortalEstimate(token) {
  const res = await fetch(`${BASE}/${token}`)
  if (!res.ok) {
    const err = new Error('Failed to load estimate')
    err.status = res.status
    throw err
  }
  return res.json()
}

export function getPortalPreviewUrl(token) {
  return `${BASE}/${token}/preview`
}

export function getPortalPdfUrl(token) {
  return `${BASE}/${token}/pdf`
}

export async function submitChangeRequest(token, message) {
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

export async function submitReject(token, name, reason) {
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

export async function submitApprove(token, data) {
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
