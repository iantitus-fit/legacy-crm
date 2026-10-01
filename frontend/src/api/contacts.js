import api from './client'

export const listContacts = async ({
  search,
  importId,
  page = 1,
  perPage = 25,
} = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (importId) params.import_id = importId
  const { data } = await api.get('/contacts', { params })
  return data
}

export const getContact = async (id) => {
  const { data } = await api.get(`/contacts/${id}`)
  return data
}

export const createContact = async (contactData) => {
  const { data } = await api.post('/contacts', contactData)
  return data
}

export const updateContact = async (id, contactData) => {
  const { data } = await api.put(`/contacts/${id}`, contactData)
  return data
}

export const deleteContact = async (id) => {
  await api.delete(`/contacts/${id}`)
}

export const searchContacts = async (query) => {
  const { data } = await api.get('/contacts/search', { params: { q: query } })
  return data
}

export const listContactTasks = async (contactId) => {
  const { data } = await api.get(`/contacts/${contactId}/tasks`)
  return data
}

export const listContactActivity = async (contactId, limit = 50) => {
  const { data } = await api.get(`/contacts/${contactId}/activity`, {
    params: { limit },
  })
  return data
}
