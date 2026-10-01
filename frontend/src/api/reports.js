import api from './client'

export const getLeadSourceReport = async (
  period = 'all',
  startDate,
  endDate
) => {
  const params = { period }
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  const { data } = await api.get('/reports/lead-sources', { params })
  return data
}

export const getLeadSourceSummary = async (period = '30d') => {
  const { data } = await api.get('/reports/lead-sources/summary', {
    params: { period },
  })
  return data
}
