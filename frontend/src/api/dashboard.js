import api from './client'

export const getDashboardStats = async () => {
  const { data } = await api.get('/dashboard/stats')
  return data
}
