import api from './client'

export const listPipelineStages = async ({ pipelineId } = {}) => {
  const params = {}
  if (pipelineId) params.pipeline_id = pipelineId
  const { data } = await api.get('/pipeline-stages', { params })
  return data
}

export const createPipelineStage = async (stageData) => {
  const { data } = await api.post('/pipeline-stages', stageData)
  return data
}

export const updatePipelineStage = async (id, stageData) => {
  const { data } = await api.put(`/pipeline-stages/${id}`, stageData)
  return data
}

export const deletePipelineStage = async (id) => {
  await api.delete(`/pipeline-stages/${id}`)
}
