import api from './client'

export const listNotes = async ({ entityType, entityId, noteType, page = 1, perPage = 50 } = {}) => {
  const params = { page, per_page: perPage }
  if (entityType) params.entity_type = entityType
  if (entityId) params.entity_id = entityId
  if (noteType) params.note_type = noteType
  const { data } = await api.get('/notes', { params })
  return data
}

export const createNote = async (noteData) => {
  const { data } = await api.post('/notes', noteData)
  return data
}

export const updateNote = async (id, noteData) => {
  const { data } = await api.put(`/notes/${id}`, noteData)
  return data
}

export const deleteNote = async (id) => {
  await api.delete(`/notes/${id}`)
}
