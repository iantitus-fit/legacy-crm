import api from './client'

export const sendChat = async ({ conversationId, entityType, entityId, message }) => {
  const { data } = await api.post('/ai/chat', {
    conversation_id: conversationId,
    entity_type: entityType,
    entity_id: entityId,
    message,
  })
  return data
}

export const listConversations = async ({ entityType, entityId } = {}) => {
  const params = {}
  if (entityType) params.entity_type = entityType
  if (entityId !== undefined && entityId !== null) params.entity_id = entityId
  const { data } = await api.get('/ai/conversations', { params })
  return data
}

export const getConversationMessages = async (conversationId, { page = 1, perPage = 50 } = {}) => {
  const { data } = await api.get(`/ai/conversations/${conversationId}/messages`, {
    params: { page, per_page: perPage },
  })
  return data
}

export const deleteConversation = async (conversationId) => {
  await api.delete(`/ai/conversations/${conversationId}`)
}

export const getBriefing = async () => {
  const { data } = await api.get('/ai/briefing')
  return data
}

export const getBriefingNarrative = async () => {
  const { data } = await api.get('/ai/briefing/narrative')
  return data
}

export const getChips = async ({ entityType } = {}) => {
  const params = {}
  if (entityType) params.entity_type = entityType
  const { data } = await api.get('/ai/chips', { params })
  return data
}
