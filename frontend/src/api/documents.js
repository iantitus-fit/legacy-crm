import api from './client'

const entityToParam = (entityType, entityId) => {
  const key =
    entityType === 'contact'
      ? 'contact_id'
      : entityType === 'job'
      ? 'job_id'
      : entityType === 'estimate'
      ? 'estimate_id'
      : null
  if (!key) throw new Error(`Unknown entityType: ${entityType}`)
  return { [key]: entityId }
}

export const listFiles = async (entityType, entityId, { folder, isPhoto } = {}) => {
  const params = entityToParam(entityType, entityId)
  if (folder !== undefined) params.folder = folder
  if (isPhoto !== undefined) params.is_photo = isPhoto
  const { data } = await api.get('/documents', { params })
  return data
}

export const listFolders = async (entityType, entityId) => {
  const params = entityToParam(entityType, entityId)
  const { data } = await api.get('/documents/folders', { params })
  return data
}

export const uploadFiles = async (
  entityType,
  entityId,
  files,
  {
    folder = 'General',
    description = null,
    showInWorkOrder = false,
    showInEstimate = false,
  } = {}
) => {
  const formData = new FormData()
  const entity = entityToParam(entityType, entityId)
  Object.entries(entity).forEach(([k, v]) => formData.append(k, v))
  formData.append('folder', folder)
  if (description) formData.append('description', description)
  formData.append('show_in_work_order', String(showInWorkOrder))
  formData.append('show_in_estimate', String(showInEstimate))
  files.forEach((f) => formData.append('files', f))
  const { data } = await api.post('/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const updateFile = async (id, patch) => {
  const body = {}
  if (patch.folder !== undefined) body.folder = patch.folder
  if (patch.description !== undefined) body.description = patch.description
  if (patch.isPhoto !== undefined) body.is_photo = patch.isPhoto
  if (patch.showInWorkOrder !== undefined)
    body.show_in_work_order = patch.showInWorkOrder
  if (patch.showInEstimate !== undefined)
    body.show_in_estimate = patch.showInEstimate
  const { data } = await api.patch(`/documents/${id}`, body)
  return data
}

export const fetchFileBlobUrl = async (id) => {
  const response = await api.get(`/documents/${id}/download`, {
    responseType: 'blob',
  })
  const type = response.headers['content-type'] || 'application/octet-stream'
  return window.URL.createObjectURL(new Blob([response.data], { type }))
}

export const downloadFile = async (id, originalFilename) => {
  const url = await fetchFileBlobUrl(id)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', originalFilename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export const deleteFile = async (id) => {
  await api.delete(`/documents/${id}`)
}

// --- Legacy aliases for code not yet migrated to the new API surface ---

export const listDocuments = async (jobId) => {
  const { data } = await api.get('/documents', { params: { job_id: jobId } })
  return data
}

export const listContactDocuments = async (contactId) => {
  const { data } = await api.get(`/contacts/${contactId}/documents`)
  return data
}

export const uploadDocuments = async (jobId, files) => {
  return uploadFiles('job', jobId, files)
}

export const uploadContactDocuments = async (contactId, files) => {
  return uploadFiles('contact', contactId, files)
}

export const downloadDocument = downloadFile
export const deleteDocument = deleteFile
