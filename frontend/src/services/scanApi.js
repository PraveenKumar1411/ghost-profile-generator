import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
  timeout: 15000,
})

export async function scanUsername(username) {
  const { data } = await api.get(`/scan/${encodeURIComponent(username)}`)
  return data
}

export async function startScan(username) {
  const { data } = await api.post('/scan/start', { username })
  return data
}

export async function getScanStatus(scanId) {
  const { data } = await api.get(`/scan/status/${encodeURIComponent(scanId)}`)
  return data
}

export async function getScanResult(scanId) {
  const { data } = await api.get(`/scan/result/${encodeURIComponent(scanId)}`)
  return data
}

export async function downloadReport(value, byReportId = false) {
  const path = byReportId ? `/report/id/${encodeURIComponent(value)}` : `/report/${encodeURIComponent(value)}`
  const { data } = await api.get(path, {
    responseType: 'blob',
  })
  return data
}

export async function getScanHistory() {
  const { data } = await api.get('/scans')
  return data
}

export async function getAnalytics() {
  const { data } = await api.get('/scans/analytics/summary')
  return data
}

export async function getSystemStatus() {
  const { data } = await api.get('/health')
  return data
}

export function getApiErrorMessage(error) {
  if (error.response?.data?.detail) return error.response.data.detail
  if (error.message) return error.message
  if (error.code === 'ECONNABORTED') return 'The scan timed out. Please try again.'
  if (!error.response) return 'Unable to reach the scanner. Is the API running?'
  return 'The scan could not be completed. Please try again.'
}
