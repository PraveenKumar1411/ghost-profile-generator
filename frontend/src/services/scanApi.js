import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
  timeout: 15000,
})

export async function scanUsername(username) {
  const { data } = await api.get(`/scan/${encodeURIComponent(username)}`)
  return data
}

export async function downloadReport(username) {
  const { data } = await api.get(`/report/${encodeURIComponent(username)}`, {
    responseType: 'blob',
  })
  return data
}

export async function getScanHistory() {
  const { data } = await api.get('/scans')
  return data
}

export function getApiErrorMessage(error) {
  if (error.response?.data?.detail) return error.response.data.detail
  if (error.code === 'ECONNABORTED') return 'The scan timed out. Please try again.'
  if (!error.response) return 'Unable to reach the scanner. Is the API running?'
  return 'The scan could not be completed. Please try again.'
}
