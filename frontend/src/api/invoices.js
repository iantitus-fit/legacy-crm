import api from './client'

export const listInvoices = async ({ search, status, estimateId, page = 1, perPage = 25 } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (status) params.status = status
  if (estimateId) params.estimate_id = estimateId
  const { data } = await api.get('/invoices', { params })
  return data
}

export const getInvoice = async (id) => {
  const { data } = await api.get(`/invoices/${id}`)
  return data
}

export const createInvoice = async (invoiceData) => {
  const { data } = await api.post('/invoices', invoiceData)
  return data
}

// Sprint 15d — deposit invoice from an estimate without changing status
export const createDepositInvoice = async ({ estimateId, depositPercent }) => {
  const { data } = await api.post('/invoices/deposit', {
    estimate_id: estimateId,
    deposit_percent: String(depositPercent),
  })
  return data
}

export const updateInvoice = async (id, invoiceData) => {
  const { data } = await api.put(`/invoices/${id}`, invoiceData)
  return data
}

export const deleteInvoice = async (id) => {
  await api.delete(`/invoices/${id}`)
}

export const addInvoiceItem = async (invoiceId, itemData) => {
  const { data } = await api.post(`/invoices/${invoiceId}/items`, itemData)
  return data
}

export const updateInvoiceItem = async (invoiceId, itemId, itemData) => {
  const { data } = await api.put(`/invoices/${invoiceId}/items/${itemId}`, itemData)
  return data
}

export const deleteInvoiceItem = async (invoiceId, itemId) => {
  await api.delete(`/invoices/${invoiceId}/items/${itemId}`)
}

export const sendInvoice = async (id, sendData) => {
  const { data } = await api.post(`/invoices/${id}/send`, sendData)
  return data
}

// Payments
export const listPayments = async (invoiceId) => {
  const { data } = await api.get(`/invoices/${invoiceId}/payments`)
  return data
}

export const recordPayment = async (invoiceId, paymentData) => {
  const { data } = await api.post(`/invoices/${invoiceId}/payments`, paymentData)
  return data
}

export const updatePayment = async (invoiceId, paymentId, paymentData) => {
  const { data } = await api.put(`/invoices/${invoiceId}/payments/${paymentId}`, paymentData)
  return data
}

export const deletePayment = async (invoiceId, paymentId) => {
  await api.delete(`/invoices/${invoiceId}/payments/${paymentId}`)
}

export const sendReceipt = async (invoiceId, paymentId, receiptData) => {
  const { data } = await api.post(`/invoices/${invoiceId}/payments/${paymentId}/send-receipt`, receiptData)
  return data
}
