import api from './client'

export const login = async (email, password) => {
  const { data } = await api.post('/auth/login', { email, password })
  return data
}

export const setup = async (email, fullName, password) => {
  const { data } = await api.post('/auth/setup', {
    email,
    full_name: fullName,
    password,
  })
  return data
}

export const getMe = async () => {
  const { data } = await api.get('/auth/me')
  return data
}

export const registerUser = async (email, fullName, password) => {
  const { data } = await api.post('/auth/register', {
    email,
    full_name: fullName,
    password,
  })
  return data
}
