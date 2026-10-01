import api from './client'

export const listTasks = async ({ jobId, status, dueDateFrom, dueDateTo, assignedToUserId, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (jobId) params.job_id = jobId
  if (status) params.status = status
  if (dueDateFrom) params.due_date_from = dueDateFrom
  if (dueDateTo) params.due_date_to = dueDateTo
  if (assignedToUserId) params.assigned_to_user_id = assignedToUserId
  const { data } = await api.get('/tasks', { params })
  return data
}

export const getTask = async (id) => {
  const { data } = await api.get(`/tasks/${id}`)
  return data
}

export const createTask = async (taskData) => {
  const { data } = await api.post('/tasks', taskData)
  return data
}

export const updateTask = async (id, taskData) => {
  const { data } = await api.put(`/tasks/${id}`, taskData)
  return data
}

export const toggleTask = async (id) => {
  const { data } = await api.patch(`/tasks/${id}/complete`)
  return data
}

export const deleteTask = async (id) => {
  await api.delete(`/tasks/${id}`)
}
