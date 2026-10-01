import api from './client'

export const createChangeOrder = async (estimateId, data = {}) => {
  const { data: result } = await api.post(`/estimates/${estimateId}/change-orders`, data)
  return result
}

export const listChangeOrders = async (estimateId) => {
  const { data } = await api.get(`/estimates/${estimateId}/change-orders`)
  return data
}

export const getChangeOrder = async (coId) => {
  const { data } = await api.get(`/change-orders/${coId}`)
  return data
}

export const updateChangeOrder = async (coId, data) => {
  const { data: result } = await api.put(`/change-orders/${coId}`, data)
  return result
}

export const deleteChangeOrder = async (coId) => {
  await api.delete(`/change-orders/${coId}`)
}

export const addChangeOrderItem = async (coId, itemData) => {
  const { data } = await api.post(`/change-orders/${coId}/items`, itemData)
  return data
}

export const updateChangeOrderItem = async (coId, itemId, itemData) => {
  const { data } = await api.put(`/change-orders/${coId}/items/${itemId}`, itemData)
  return data
}

export const deleteChangeOrderItem = async (coId, itemId) => {
  await api.delete(`/change-orders/${coId}/items/${itemId}`)
}

export const duplicateChangeOrderItem = async (coId, itemId) => {
  const { data } = await api.post(`/change-orders/${coId}/items/${itemId}/duplicate`)
  return data
}

export const sendChangeOrder = async (coId, data) => {
  const { data: result } = await api.post(`/change-orders/${coId}/send`, data)
  return result
}
