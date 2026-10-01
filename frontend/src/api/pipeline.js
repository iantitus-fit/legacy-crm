import api from './client'

export const listPipelines = async () => {
  const { data } = await api.get('/pipelines')
  return data
}

export const getPipeline = async (id) => {
  const { data } = await api.get(`/pipelines/${id}`)
  return data
}

export const getPipelineBoard = async (pipelineId, filters = {}) => {
  const params = {}
  if (filters.salesperson) params.salesperson = filters.salesperson
  if (filters.lead_source) params.lead_source = filters.lead_source
  if (filters.label) params.label = filters.label
  if (filters.created_after) params.created_after = filters.created_after
  if (filters.created_before) params.created_before = filters.created_before
  const { data } = await api.get(`/pipelines/${pipelineId}/board`, { params })
  return data
}

// Sprint 15c — contact-centric board for Lead/Sales pipelines
export const getContactsBoard = async (pipelineId) => {
  const { data } = await api.get(`/pipelines/${pipelineId}/contacts-board`)
  return data
}

// Sprint 15c — estimate-centric board for the Jobs pipeline
export const getEstimatesBoard = async (pipelineId) => {
  const { data } = await api.get(`/pipelines/${pipelineId}/estimates-board`)
  return data
}

export const addStage = async (pipelineId, stageData) => {
  const { data } = await api.post(`/pipelines/${pipelineId}/stages`, stageData)
  return data
}

export const updateStage = async (pipelineId, stageId, stageData) => {
  const { data } = await api.put(`/pipelines/${pipelineId}/stages/${stageId}`, stageData)
  return data
}

export const deleteStage = async (pipelineId, stageId) => {
  await api.delete(`/pipelines/${pipelineId}/stages/${stageId}`)
}

export const reorderStages = async (pipelineId, stages) => {
  const { data } = await api.put(`/pipelines/${pipelineId}/stages/reorder`, { stages })
  return data
}
