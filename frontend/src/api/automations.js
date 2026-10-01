import api from './client'

// ---------- Sequences ----------
export const listSequences = async () => {
  const { data } = await api.get('/automations/sequences')
  return data
}

export const getSequence = async (id) => {
  const { data } = await api.get(`/automations/sequences/${id}`)
  return data
}

export const createSequence = async (sequenceData) => {
  const { data } = await api.post('/automations/sequences', sequenceData)
  return data
}

export const updateSequence = async (id, sequenceData) => {
  const { data } = await api.put(`/automations/sequences/${id}`, sequenceData)
  return data
}

export const toggleSequence = async (id) => {
  const { data } = await api.put(`/automations/sequences/${id}/toggle`)
  return data
}

export const deleteSequence = async (id) => {
  await api.delete(`/automations/sequences/${id}`)
}

// ---------- Steps ----------
export const createStep = async (sequenceId, stepData) => {
  const { data } = await api.post(
    `/automations/sequences/${sequenceId}/steps`,
    stepData,
  )
  return data
}

export const updateStep = async (stepId, stepData) => {
  const { data } = await api.put(`/automations/steps/${stepId}`, stepData)
  return data
}

export const deleteStep = async (stepId) => {
  await api.delete(`/automations/steps/${stepId}`)
}

export const reorderSteps = async (sequenceId, items) => {
  const { data } = await api.put(
    `/automations/sequences/${sequenceId}/steps/reorder`,
    { items },
  )
  return data
}

// ---------- Enrollments ----------
export const listEnrollments = async ({
  sequenceId,
  contactId,
  status,
  limit = 100,
} = {}) => {
  const params = { limit }
  if (sequenceId !== undefined) params.sequence_id = sequenceId
  if (contactId !== undefined) params.contact_id = contactId
  if (status) params.status = status
  const { data } = await api.get('/automations/enrollments', { params })
  return data
}

export const getContactEnrollments = async (contactId) => {
  const { data } = await api.get(`/automations/contacts/${contactId}`)
  return data
}

export const manualEnroll = async (contactId, sequenceId) => {
  const { data } = await api.post('/automations/enroll', {
    contact_id: contactId,
    sequence_id: sequenceId,
  })
  return data
}

export const stopEnrollment = async (enrollmentId, reason) => {
  const { data } = await api.put(
    `/automations/enrollments/${enrollmentId}/stop`,
    { reason: reason || null },
  )
  return data
}

// ---------- Contact toggle ----------
export const toggleContactAutomations = async (contactId, enabled) => {
  const { data } = await api.put(
    `/automations/contacts/${contactId}/toggle`,
    { automations_enabled: enabled },
  )
  return data
}

// ---------- Dashboard + logs ----------
export const getAutomationDashboard = async () => {
  const { data } = await api.get('/automations/dashboard')
  return data
}

export const listAutomationLogs = async ({
  sequenceId,
  contactId,
  status,
  limit = 100,
} = {}) => {
  const params = { limit }
  if (sequenceId !== undefined) params.sequence_id = sequenceId
  if (contactId !== undefined) params.contact_id = contactId
  if (status) params.status = status
  const { data } = await api.get('/automations/logs', { params })
  return data
}
