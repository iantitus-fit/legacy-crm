import api from './client'

export const listLeads = async ({ search, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  const { data } = await api.get('/leads', { params })
  return data
}

export const getLead = async (id) => {
  const { data } = await api.get(`/leads/${id}`)
  return data
}

export const createLead = async (leadData) => {
  const { data } = await api.post('/leads', leadData)
  return data
}

export const updateLead = async (id, leadData) => {
  const { data } = await api.put(`/leads/${id}`, leadData)
  return data
}

export const deleteLead = async (id) => {
  await api.delete(`/leads/${id}`)
}

export const convertLead = async (id, convertData) => {
  const { data } = await api.post(`/leads/${id}/convert`, convertData)
  return data
}
