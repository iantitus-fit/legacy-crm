import api from './client'

export const sendSms = async (contactId, body) => {
  const { data } = await api.post('/sms/send', {
    contact_id: contactId,
    body,
  })
  return data
}

export const getConversation = async (contactId, { page = 1, perPage = 50 } = {}) => {
  const { data } = await api.get(`/contacts/${contactId}/sms`, {
    params: { page, per_page: perPage },
  })
  return data
}

export const sendEstimateViaSms = async (contactId, estimateId) => {
  const { data } = await api.post('/sms/send-estimate', {
    contact_id: contactId,
    estimate_id: estimateId,
  })
  return data
}

export const getSmsConfig = async () => {
  const { data } = await api.get('/sms/config')
  return data
}

export const updateSmsConfig = async (config) => {
  const { data } = await api.put('/sms/config', config)
  return data
}
