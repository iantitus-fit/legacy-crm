import api from './client'

export const fetchWorkOrderBlobUrl = async (estimateId, secret = false) => {
  const response = await api.get(`/estimates/${estimateId}/work-order`, {
    params: { secret },
    responseType: 'blob',
  })
  const type = response.headers['content-type'] || 'application/pdf'
  return window.URL.createObjectURL(new Blob([response.data], { type }))
}

export const sendWorkOrder = async (estimateId, { recipientEmail, secret = false, message = null }) => {
  const { data } = await api.post(`/estimates/${estimateId}/work-order/send`, {
    recipient_email: recipientEmail,
    secret,
    message,
  })
  return data
}

export const getWorkOrderLink = async (estimateId, secret = false) => {
  const { data } = await api.post(
    `/estimates/${estimateId}/work-order/link`,
    null,
    { params: { secret } }
  )
  return data
}
