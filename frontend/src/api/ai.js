import api from './client'

export const generateAI = async ({ eventType, contactId, estimateId, extra }) => {
  const { data } = await api.post('/ai/generate', {
    event_type: eventType,
    contact_id: contactId,
    estimate_id: estimateId,
    extra,
  })
  return data
}

export const useAIAction = async (actionId) => {
  const { data } = await api.post(`/ai/actions/${actionId}/use`)
  return data
}

export const dismissAIAction = async (actionId) => {
  const { data } = await api.post(`/ai/actions/${actionId}/dismiss`)
  return data
}

export const listAIActions = async ({ contactId, estimateId, eventType, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (contactId) params.contact_id = contactId
  if (estimateId) params.estimate_id = estimateId
  if (eventType) params.event_type = eventType
  const { data } = await api.get('/ai/actions', { params })
  return data
}

export const getAIStats = async () => {
  const { data } = await api.get('/ai/stats')
  return data
}
