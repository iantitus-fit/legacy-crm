import api from './client'

export const previewImport = async (file) => {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/import/contacts/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const confirmImport = async ({ previewToken, fieldMappings, options }) => {
  const { data } = await api.post('/import/contacts/confirm', {
    preview_token: previewToken,
    field_mappings: fieldMappings,
    options,
  })
  return data
}

export const listImportHistory = async ({ page = 1, perPage = 25 } = {}) => {
  const { data } = await api.get('/import/history', {
    params: { page, per_page: perPage },
  })
  return data
}

export const undoImport = async (importId) => {
  const { data } = await api.post(`/import/contacts/${importId}/undo`)
  return data
}
