import api from './client'

export const listMaterials = async ({ search, category, priceListId, flagged, page = 1, perPage = 50 } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (category) params.category = category
  if (priceListId) params.price_list_id = priceListId
  if (flagged) params.flagged = 'true'
  const { data } = await api.get('/materials', { params })
  return data
}

export const getMaterial = async (id) => {
  const { data } = await api.get(`/materials/${id}`)
  return data
}

export const createMaterial = async (materialData) => {
  const { data } = await api.post('/materials', materialData)
  return data
}

export const updateMaterial = async (id, materialData) => {
  const { data } = await api.put(`/materials/${id}`, materialData)
  return data
}

export const deleteMaterial = async (id) => {
  await api.delete(`/materials/${id}`)
}

export const listCategories = async () => {
  const { data } = await api.get('/materials/categories')
  return data
}

export const importMaterials = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/materials/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
