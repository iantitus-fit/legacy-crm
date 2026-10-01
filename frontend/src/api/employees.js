import api from './client'

export const listEmployees = async ({ search, role, isActive, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (role) params.role = role
  if (isActive !== undefined) params.is_active = isActive
  const { data } = await api.get('/employees', { params })
  return data
}

export const getEmployee = async (id) => {
  const { data } = await api.get(`/employees/${id}`)
  return data
}

export const createEmployee = async (employeeData) => {
  const { data } = await api.post('/employees', employeeData)
  return data
}

export const updateEmployee = async (id, employeeData) => {
  const { data } = await api.put(`/employees/${id}`, employeeData)
  return data
}

export const deleteEmployee = async (id) => {
  await api.delete(`/employees/${id}`)
}
