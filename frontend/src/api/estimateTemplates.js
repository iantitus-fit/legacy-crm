import api from './client'

export const listTemplates = async () => {
  const { data } = await api.get('/estimate-templates')
  return data
}

export const getTemplate = async (id) => {
  const { data } = await api.get(`/estimate-templates/${id}`)
  return data
}

export const createTemplate = async (templateData) => {
  const { data } = await api.post('/estimate-templates', templateData)
  return data
}

export const updateTemplate = async (id, templateData) => {
  const { data } = await api.put(`/estimate-templates/${id}`, templateData)
  return data
}

export const deleteTemplate = async (id) => {
  await api.delete(`/estimate-templates/${id}`)
}

export const duplicateTemplate = async (id) => {
  const { data } = await api.post(`/estimate-templates/${id}/duplicate`)
  return data
}

export const addTemplateItem = async (templateId, itemData) => {
  const { data } = await api.post(`/estimate-templates/${templateId}/items`, itemData)
  return data
}

export const updateTemplateItem = async (templateId, itemId, itemData) => {
  const { data } = await api.put(`/estimate-templates/${templateId}/items/${itemId}`, itemData)
  return data
}

export const deleteTemplateItem = async (templateId, itemId) => {
  await api.delete(`/estimate-templates/${templateId}/items/${itemId}`)
}

export const reorderTemplateItems = async (templateId, itemIds) => {
  const { data } = await api.put(`/estimate-templates/${templateId}/items/reorder`, { item_ids: itemIds })
  return data
}

export const previewTemplate = async (templateId, measurements) => {
  const { data } = await api.post(`/estimate-templates/${templateId}/preview`, { ...measurements })
  return data
}

export const applyTemplate = async (estimateId, templateId, measurements) => {
  const { data } = await api.post(`/estimates/${estimateId}/apply-template`, {
    template_id: templateId,
    measurements,
  })
  return data
}
