import api from './client'

export const getCalendarJobs = async ({ startDate, endDate, crewId } = {}) => {
  const params = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  if (crewId) params.crew_id = crewId
  const { data } = await api.get('/calendar/jobs', { params })
  return data
}

export const getCalendarAppointments = async ({ startDate, endDate, assignedToUserId } = {}) => {
  const params = {}
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  if (assignedToUserId) params.assigned_to_user_id = assignedToUserId
  const { data } = await api.get('/calendar/appointments', { params })
  return data
}

export const getUpcoming = async (limit = 5) => {
  const { data } = await api.get('/calendar/upcoming', { params: { limit } })
  return data
}
