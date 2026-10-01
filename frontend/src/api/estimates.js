import api from './client'

export const listEstimates = async ({ jobId, search, status, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (jobId) params.job_id = jobId
  if (search) params.search = search
  if (status) params.status = status
  const { data } = await api.get('/estimates', { params })
  return data
}

export const getEstimate = async (id) => {
  const { data } = await api.get(`/estimates/${id}`)
  return data
}

export const createEstimate = async (estimateData) => {
  const { data } = await api.post('/estimates', estimateData)
  return data
}

export const updateEstimate = async (id, estimateData) => {
  const { data } = await api.put(`/estimates/${id}`, estimateData)
  return data
}

export const deleteEstimate = async (id) => {
  await api.delete(`/estimates/${id}`)
}

export const duplicateEstimate = async (id) => {
  const { data } = await api.post(`/estimates/${id}/duplicate`)
  return data
}

// Sprint 15d — internal approve (no customer portal signature)
export const approveEstimateInternal = async (id, { signerName } = {}) => {
  const body = signerName ? { signer_name: signerName } : {}
  const { data } = await api.post(`/estimates/${id}/approve-internal`, body)
  return data
}

export const addLineItem = async (estimateId, itemData) => {
  const { data } = await api.post(`/estimates/${estimateId}/line-items`, itemData)
  return data
}

export const updateLineItem = async (estimateId, itemId, itemData) => {
  const { data } = await api.put(`/estimates/${estimateId}/line-items/${itemId}`, itemData)
  return data
}

export const deleteLineItem = async (estimateId, itemId) => {
  await api.delete(`/estimates/${estimateId}/line-items/${itemId}`)
}

export const duplicateLineItem = async (estimateId, itemId) => {
  const { data } = await api.post(`/estimates/${estimateId}/line-items/${itemId}/duplicate`)
  return data
}

export const reorderLineItems = async (estimateId, itemIds) => {
  const { data } = await api.put(`/estimates/${estimateId}/line-items/reorder`, { item_ids: itemIds })
  return data
}

export const createSection = async (estimateId, sectionData) => {
  const { data } = await api.post(`/estimates/${estimateId}/sections`, sectionData)
  return data
}

export const updateSection = async (estimateId, sectionId, sectionData) => {
  const { data } = await api.put(`/estimates/${estimateId}/sections/${sectionId}`, sectionData)
  return data
}

export const deleteSection = async (estimateId, sectionId) => {
  await api.delete(`/estimates/${estimateId}/sections/${sectionId}`)
}

export const reorderSections = async (estimateId, sectionIds) => {
  const { data } = await api.put(`/estimates/${estimateId}/sections/reorder`, { section_ids: sectionIds })
  return data
}
