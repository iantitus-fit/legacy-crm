import api from './client'

export const listJobs = async ({ search, page = 1, perPage = 25, stageId, workType, contactId, pipelineId } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (stageId) params.stage_id = stageId
  if (workType) params.work_type = workType
  if (contactId) params.contact_id = contactId
  if (pipelineId) params.pipeline_id = pipelineId
  const { data } = await api.get('/jobs', { params })
  return data
}

export const getJob = async (id) => {
  const { data } = await api.get(`/jobs/${id}`)
  return data
}

export const createJob = async (jobData) => {
  const { data } = await api.post('/jobs', jobData)
  return data
}

export const updateJob = async (id, jobData) => {
  const { data } = await api.put(`/jobs/${id}`, jobData)
  return data
}

export const updateJobStage = async (id, stageId) => {
  const { data } = await api.patch(`/jobs/${id}/stage`, { stage_id: stageId })
  return data
}

export const moveJobToPipeline = async (id, pipelineId, stageId) => {
  const payload = { pipeline_id: pipelineId }
  if (stageId) payload.stage_id = stageId
  const { data } = await api.put(`/jobs/${id}/pipeline`, payload)
  return data
}

export const scheduleJob = async (id, scheduleData) => {
  const { data } = await api.patch(`/jobs/${id}/schedule`, scheduleData)
  return data
}

export const deleteJob = async (id) => {
  await api.delete(`/jobs/${id}`)
}
