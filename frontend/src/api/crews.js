import api from './client'

export const listCrews = async ({ isActive, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (isActive !== undefined) params.is_active = isActive
  const { data } = await api.get('/crews', { params })
  return data
}

export const getCrew = async (id) => {
  const { data } = await api.get(`/crews/${id}`)
  return data
}

export const createCrew = async (crewData) => {
  const { data } = await api.post('/crews', crewData)
  return data
}

export const updateCrew = async (id, crewData) => {
  const { data } = await api.put(`/crews/${id}`, crewData)
  return data
}

export const deleteCrew = async (id) => {
  await api.delete(`/crews/${id}`)
}
