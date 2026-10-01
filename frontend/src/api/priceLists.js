import api from './client'

export const listPriceLists = async () => {
  const { data } = await api.get('/price-lists')
  return data
}

export const updatePriceList = async (id, priceListData) => {
  const { data } = await api.put(`/price-lists/${id}`, priceListData)
  return data
}
