import api from './client'

export const listAppointments = async ({ assignedToUserId, appointmentType, startDate, endDate, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (assignedToUserId) params.assigned_to_user_id = assignedToUserId
  if (appointmentType) params.appointment_type = appointmentType
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  const { data } = await api.get('/appointments', { params })
  return data
}

export const getAppointment = async (id) => {
  const { data } = await api.get(`/appointments/${id}`)
  return data
}

export const createAppointment = async (appointmentData) => {
  const { data } = await api.post('/appointments', appointmentData)
  return data
}

export const updateAppointment = async (id, appointmentData) => {
  const { data } = await api.put(`/appointments/${id}`, appointmentData)
  return data
}

export const deleteAppointment = async (id) => {
  await api.delete(`/appointments/${id}`)
}
